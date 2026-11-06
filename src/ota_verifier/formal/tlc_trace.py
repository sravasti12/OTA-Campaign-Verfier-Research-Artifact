"""Parse TLC's text output into structured counterexample traces."""
import re
from typing import Any

STATE_HEADER = re.compile(r'^State (\d+): (?:<(\w+)\b.*>|(Stuttering))\s*$')
LOOP_HEADER = re.compile(r'^Back to state (\d+)')
VARIABLE = re.compile(r'^/\\ (\w+) = (.*)$')
TOKEN = re.compile(r'\s*(\|->|"[^"]*"|-?\d+|TRUE|FALSE|\w+|[\[\]{},])')


def parse_value(text: str) -> Any:
    """Parse the subset of TLA+ values TLC prints: records, sets, strings, numbers, booleans."""
    tokens = TOKEN.findall(text)
    value, position = _value(tokens, 0)
    if position != len(tokens):
        raise ValueError(f'Trailing input in TLA+ value: {text!r}')
    return value


def _value(tokens: list[str], index: int) -> tuple[Any, int]:
    token = tokens[index]
    if token == '[':
        return _record(tokens, index + 1)
    if token == '{':
        return _set(tokens, index + 1)
    if token.startswith('"'):
        return token[1:-1], index + 1
    if token in ('TRUE', 'FALSE'):
        return token == 'TRUE', index + 1
    if re.fullmatch(r'-?\d+', token):
        return int(token), index + 1
    raise ValueError(f'Unexpected TLA+ token: {token!r}')


def _record(tokens: list[str], index: int) -> tuple[dict[str, Any], int]:
    record: dict[str, Any] = {}
    while tokens[index] != ']':
        key = tokens[index]
        if tokens[index + 1] != '|->':
            raise ValueError(f'Expected |-> after {key!r}')
        record[key], index = _value(tokens, index + 2)
        if tokens[index] == ',':
            index += 1
    return record, index + 1


def _set(tokens: list[str], index: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while tokens[index] != '}':
        item, index = _value(tokens, index)
        items.append(item)
        if tokens[index] == ',':
            index += 1
    return sorted(items), index + 1


def _variables(lines: list[str]) -> dict[str, Any]:
    """Join values TLC wrapped over several lines, then parse each one."""
    joined: list[str] = []
    for line in lines:
        if line.startswith('/\\ '):
            joined.append(line)
        elif joined:
            joined[-1] += ' ' + line.strip()
    state = {}
    for line in joined:
        match = VARIABLE.match(line)
        if match is None:
            raise ValueError(f'Unreadable state line: {line!r}')
        state[match[1]] = parse_value(match[2])
    return state


def parse_trace(output: str) -> dict[str, Any]:
    """Return the states of the error trace, and how a liveness trace ends.

    `ending` is 'stuttering' when the system stops forever in the last state,
    'loop' when it cycles back to `loop_to`, and 'finite' for a safety trace.
    """
    states: list[dict[str, Any]] = []
    ending, loop_to = 'finite', None
    block: list[str] | None = None
    action = None

    def close() -> None:
        nonlocal block
        if block is not None:
            states.append({'action': action, 'vars': _variables(block)})
        block = None

    for line in output.splitlines():
        header = STATE_HEADER.match(line)
        loop = LOOP_HEADER.match(line)
        if header:
            close()
            if header[3]:
                ending = 'stuttering'
            else:
                action = header[2]
                block = []
        elif loop:
            close()
            ending, loop_to = 'loop', int(loop[1])
        elif block is not None:
            if line.startswith('/\\ ') or (line.startswith(' ') and block):
                block.append(line)
            else:
                close()
    close()
    return {'states': states, 'ending': ending, 'loop_to': loop_to}


def changed_ecus(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Name the ECUs a step touched; TLC does not print action arguments."""
    names = set()
    for variable in ('active', 'inactive', 'stage', 'corrupt'):
        names |= {ecu for ecu, value in after[variable].items() if before[variable][ecu] != value}
    return sorted(names)
