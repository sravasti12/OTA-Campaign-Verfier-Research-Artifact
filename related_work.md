# Related work

The paper cites only entries in **A** to **C**, and only for what the "Read" column supports. Anything in **D** must not be cited. Bibliographic details for every DOI and arXiv entry are in [paper/citations_verified.json](paper/citations_verified.json), fetched from Crossref and arXiv by `python paper/verify_citations.py`. `paper/refs.bib` copies them.

Last updated 2026-11-08.

**How the search was done:**
- Searched: Crossref, arXiv, OpenAlex, Semantic Scholar and web search, plus the reference lists of Hagen et al. and Lorch et al.
- Not searched: **IEEE Xplore and Scopus**, which need a subscription login. The paper states this as a limitation.

**What "read" means:**
- **Full**: the whole text was extracted and searched by topic, and the abstract, contributions, related work, conclusion and every passage on rollback, dependencies and partial failure were read.
- **Abstract**: only the abstract or the publisher record was read.

## A. Vehicle and OTA update work

| Key | Reference | Read | How this paper differs |
| --- | --- | --- | --- |
| hagen2026 | Hagen, Lundqvist, Phu, Wang, Strandberg, Schiller. Towards a Formal Verification of Secure Vehicle Software Updates. *Computers & Security* 161, 104751, 2026. doi:10.1016/j.cose.2025.104751; arXiv:2511.15479 | Full (arXiv) | ProVerif security proof of UniSUF under a Dolev–Yao attacker; liveness is argued, not proved. They name multi-ECU extension as future work. We check functional safety of campaign execution under faults, with no attacker |
| lorch2024 | Lorch, Larraz, Tinelli, Chowdhury. A Comprehensive, Automated Security Analysis of the Uptane Automotive OTA Update Framework. RAID 2024, 594–612. doi:10.1145/3678890.3678927 | Full (author copy) | Kind 2 with Tamarin, nine threat models, six new vulnerabilities. Their "rollback" is a downgrade attack (P3, nondecreasing versions). Ours is recovery after failure |
| kuppusamy2016 | Kuppusamy, Brown, Awwad, McCoy, Bielawski, Mott, Lauzon, Weimerskirch, Cappos. Uptane: Securing Software Updates for Automobiles. 14th escar Europe, 2016 (uptane.org PDF) | Full | Defines "mixed-bundles" and "partial bundle installation" attacks, and notes that partial installation can happen accidentally if power runs out. We study that hazard as a consequence of the update design under faults, not of an attacker |
| kuppusamy2018 | Kuppusamy, DeLong, Cappos. Uptane: Security and Customizability of Software Updates for Vehicles. *IEEE Vehicular Technology Magazine* 13(1):66–73, 2018. doi:10.1109/MVT.2017.2778751 | Full | Uptane's director does dependency resolution to *select* images. We check which versions *run* during and after a campaign |
| samuel2010 | Samuel, Mathewson, Cappos, Dingledine. Survivable Key Compromise in Software Update Systems (TUF). CCS 2010, 61–72. doi:10.1145/1866307.1866315 | Abstract | Repository security; Uptane's predecessor |
| kirk2021 | Kirk, Nguyen, Bryans, Shaikh, Evans, Price. Formalising UPTANE in CSP for Security Testing. QRS-C 2021, 816–824. doi:10.1109/QRS-C55045.2021.00124 | Abstract | CSP plus Dolev–Yao attacker, to generate security tests. Security, not campaign safety |
| kirk2023 | Kirk, Nguyen, Bryans, Shaikh, Wartnaby. A Formal Framework for Security Testing of Automotive OTA Update Systems. *JLAMP* 130, 100812, 2023. doi:10.1016/j.jlamp.2022.100812 | Abstract | Same line as kirk2021, with testbed execution of generated tests. Closest in method to our model-versus-SIL step, but for security |
| mahmood2020 | Mahmood, Fouillade, Nguyen, Shaikh. A Model-Based Security Testing Approach for Automotive OTA Updates. ICSTW 2020, 6–13. doi:10.1109/ICSTW50294.2020.00019 | Abstract | Attack-tree-based test generation. Security testing |
| mahmood2022 | Mahmood, Nguyen, Shaikh. Systematic Threat Assessment and Security Testing of Automotive OTA Updates. *Vehicular Communications* 35, 100468, 2022. doi:10.1016/j.vehcom.2022.100468 | Abstract (truncated) | Threat assessment and security testing |
| boureanu2023 | Boureanu. Formally Verifying the Security and Privacy of an Adopted Standard for Software-Update in Cars: Verifying Uptane 2.0. IEEE SMC 2023, 1301–1306. doi:10.1109/SMC53992.2023.10394216 | Abstract | Tamarin, security and privacy |
| pedroza2011 | Pedroza, Idrees, Apvrille, Roudier. A Formal Methodology Applied to Secure Over-the-Air Automotive Applications. IEEE VTC Fall 2011, 1–5. doi:10.1109/VETECF.2011.6093061 | Full (EURECOM copy) | Extends a safety framework (UPPAAL) to security, applied to a firmware update protocol between a communication unit and one ECU. Reported results are security properties. **Closest earlier safety-aware work.** We model a campaign over many dependent ECUs |
| idrees2011 | Idrees, Schweppe, Roudier, Wolf, Scheuermann, Henniger. Secure Automotive On-Board Protocols: A Case of Over-the-Air Firmware Updates. Nets4Cars 2011, LNCS, 224–238. doi:10.1007/978-3-642-19786-4_20 | Record only | Cited only as the source of the protocol Pedroza et al. verified |
| ponsard2021 | Ponsard, Darquennes. Towards Formal Security Verification of OTA Update Protocol: Requirements, Survey and UpKit Case Study. ICISSP 2021, 800–808. doi:10.5220/0010431408000808 | Record only. Content via Hagen et al.'s description, which the paper says | Tamarin, IoT update protocol |
| mukherjee2021 | Mukherjee, Gerdes, Chantem. Trusted Verification of OTA Secure Software Updates on COTS Embedded Systems. AutoSec 2021 (NDSS workshop). doi:10.14722/autosec.2021.23028 | Full (NDSS PDF) | Uptane in a TEE, code checked with SAW. Implementation security |
| shoker2023 | Shoker, Alves, Esteves-Verissimo. ScalOTA. arXiv:2307.02032 | Abstract | Scalable distribution and chain of trust |
| mostafa2025 | Mostafa, Mohamed, Ezzat. Enhancing AUTOSAR-Based FOTA ... on a Steering System. arXiv:2503.05839 | Abstract | Single-ECU FOTA implementation |
| li2024 | Li et al. OTA Upgrading for Enhancing Security of Intelligent Connected Vehicles: A Survey. *Artificial Intelligence Review* 57(11):314, 2024. doi:10.1007/s10462-024-10968-z | Abstract | Survey, security focus |
| liotou2026 | Liotou, Tzelalidou, Christodoulou. The Rise of the Software-Defined Vehicle. arXiv:2605.30001 | Abstract | SDV survey |
| schmid2021 | Schmid et al. Formal Verification of a Fail-Operational Automotive Driving System. arXiv:2101.07307 | Abstract | Model checking for ISO 26262 evidence, on runtime arbitration, not updates |

## B. Methods

| Key | Reference | Read | Used for |
| --- | --- | --- | --- |
| lamport1994 | Lamport. The Temporal Logic of Actions. *TOPLAS* 16(3):872–923, 1994. doi:10.1145/177492.177726 | Record | TLA semantics |
| yu1999 | Yu, Manolios, Lamport. Model Checking TLA+ Specifications. CHARME 1999, LNCS 1703, 54–66. doi:10.1007/3-540-48153-2_6 | Record | TLC |
| konnov2019 | Konnov, Kukovec, Tran. TLA+ Model Checking Made Symbolic. *PACMPL* 3(OOPSLA):1–30, 2019. doi:10.1145/3360549 | Record | Apalache, as an alternative not used |
| cousineau2012 | Cousineau, Doligez, Lamport, Merz, Ricketts, Vanzetto. TLA+ Proofs. FM 2012, LNCS, 147–154. doi:10.1007/978-3-642-32759-9_14 | Record | TLAPS, for mechanizing Theorem 1 later |
| newcombe2015 | Newcombe et al. How Amazon Web Services Uses Formal Methods. *CACM* 58(4):66–73, 2015. doi:10.1145/2699417 | Record | TLA+ in industry |
| clarke1989 | Clarke, Long, McMillan. Compositional Model Checking. LICS 1989, 353–362. doi:10.1109/LICS.1989.39190 | Record | Compositional reasoning |
| clarke1994 | Clarke, Grumberg, Long. Model Checking and Abstraction. *TOPLAS* 16(5):1512–1542, 1994. doi:10.1145/186025.186051 | Record | Safety-preserving over-approximation |
| abadi1991 | Abadi, Lamport. The Existence of Refinement Mappings. *TCS* 82(2):253–284, 1991. doi:10.1016/0304-3975(91)90224-P | Record | Refinement mapping |
| emerson1995 | Emerson, Namjoshi. Reasoning About Rings. POPL 1995, 85–94. doi:10.1145/199448.199468 | Record | Cutoffs |
| cirstea2024 | Cirstea, Kuppe, Loillier, Merz. Validating Traces of Distributed Programs Against TLA+ Specifications. arXiv:2404.16075 | Abstract | Trace validation |
| howard2024 | Howard, Kuppe, Ashton, Chamayou, Crooks. Smart Casual Verification of the Confidential Consortium Framework. arXiv:2406.17455 (current arXiv title) | Abstract | Linking TLA+ to an implementation |

## C. Regulation, standards and tools

| Key | Item | Read |
| --- | --- | --- |
| unr156 | UN Regulation No 156, OJ L 82, 9.3.2021, pp. 60–74 (EUR-Lex, ELI reg/2021/388) | Full text. Paragraphs used: 7.1.1.5 (interdependencies), 7.1.1.7 (compatibility before issue), 7.2.2.1.1 (restore previous version or safe state after a failed or interrupted update) |
| iso24089 | ISO 24089:2023 Road vehicles — Software update engineering (iso.org/standard/77796) | Abstract and scope only. The standard text is paid and not read |
| tlaplus | TLA+ tools v1.7.4 (TLC 2.19) | SHA-256 in `tools/versions.json` |
| mcuboot | MCUboot v2.4.0 | Pinned in `docs/MCUBOOT_VALIDATION_REPORT.md`. Not cited in the paper |
| abfirmware | navadiashrey/ab-firmware-update-tla, GitHub | Project description only. Not peer-reviewed, not cited |

## D. Not found or not verified: do not cite

| Item | Status |
| --- | --- |
| "Weiß 2025" and "Dharavath 2026" | **Not found** under these names in Crossref, arXiv, OpenAlex or web search on 2026-11-08. A title, DOI or arXiv ID is needed |
| Davis, Hirschhorn, Schvimer. eXtreme Modelling in Practice. PVLDB 2020 | The DOI recorded earlier resolves to a different paper. Dropped |
| AUTOSAR UCM and FOTA explanation documents | Not read |
| ISO 26262 | Not read. Mentioned only as cited by Schmid et al. |
| "OTA Update Assurance for Energy and Charging Functions in SDVs" | ResearchGate listing only |
| DataMod 2024 lifecycle-verification paper | Title and authors unconfirmed |
| Behrmann, David, Larsen. UPPAAL tutorial | Not looked up |
