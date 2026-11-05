"""Durable response journal: committed outputs replay; uncertain calls never retry."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from ..llm.client import JsonClient, LLMError
from ..llm.evidence import canonical_json, content_hash
from ..llm.models import CallRecord, Purpose
from .recipes import RoleRecipe
from .store import RunStore, StorageError, UncertainModelCall


@dataclass
class ReceiptClient:
    """One role bound to an immutable profile and graph thread."""
    store: RunStore
    thread_id: str
    purpose: Purpose
    recipe: RoleRecipe
    client: Callable[[], JsonClient]

    def generate_json(self, *, purpose: Purpose, system_prompt: str, user_prompt: str,
                      schema: dict[str, Any], prompt_version: str) -> CallRecord:
        """Reuse exact saved evidence or commit request intent before contacting a model."""
        if purpose != self.purpose:
            raise ValueError('Receipt role differs from requested model purpose')
        fingerprint = content_hash(canonical_json({'purpose': purpose, 'system': system_prompt,
            'user': user_prompt, 'schema': schema, 'prompt_version': prompt_version,
            'profile': self.recipe.model_dump(mode='json')}))
        receipt = self.store.receipt(self.thread_id, purpose, fingerprint)
        if receipt is not None:
            if receipt['status'] in ('inflight', 'uncertain'):
                raise UncertainModelCall('A prior provider request may have completed; start a new revision to retry explicitly')
            if receipt['call_json'] and content_hash(receipt['call_json']) != receipt['call_hash']:
                raise StorageError('Saved response receipt hash mismatch')
            record = CallRecord.model_validate_json(receipt['call_json']) if receipt['call_json'] else None
            if receipt['error']:
                raise LLMError(receipt['error'], record)
            if record is None or record.purpose != purpose:
                raise ValueError('Saved response receipt is malformed')
            return record
        # Configuration validation happens before intent; a missing key has not
        # sent a request and therefore does not become an uncertain provider call.
        real_client = self.client()
        self.store.begin_receipt(self.thread_id, purpose, fingerprint)
        try:
            record = real_client.generate_json(purpose=purpose, system_prompt=system_prompt,
                user_prompt=user_prompt, schema=schema, prompt_version=prompt_version)
        except LLMError as error:
            if error.record is not None or self.recipe.kind != 'provider' or '(HTTP ' in str(error):
                self.store.finish_receipt(self.thread_id, purpose, fingerprint, 'rejected',
                    error.record.model_dump_json() if error.record else None, str(error))
                raise
            self.store.finish_receipt(self.thread_id, purpose, fingerprint, 'uncertain', None,
                                      'Provider request outcome is uncertain')
            raise UncertainModelCall('Provider request outcome is uncertain; no automatic retry was performed') from None
        except BaseException:
            self.store.finish_receipt(self.thread_id, purpose, fingerprint, 'uncertain', None,
                                      'Model request interrupted; outcome is uncertain')
            raise
        self.store.finish_receipt(self.thread_id, purpose, fingerprint, 'complete', record.model_dump_json(), None)
        return record
