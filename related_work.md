# Related work

The paper may cite only papers in **A** or **B**, and only for what the "Checked" column supports. Anything in **C** must appear in the paper as TODO until checked. Add or promote entries here, and record what was
checked. Nothing here has been read in full unless it says so.

Last updated 2026-11-06. The week 2 systematic search has not been done, so this list is incomplete, and **novelty is not established**.

## A. Details verified, usable for general statements about the work

| Key | Reference | Checked | May be cited for |
| --- | --- | --- | --- |
| yu1999 | Yuan Yu, Panagiotis Manolios, Leslie Lamport. Model Checking TLA+ Specifications. CHARME 1999, LNCS 1703, pp. 54-66 | Details and abstract summary | TLC as an explicit-state checker for TLA+ |
| konnov2019 | Konnov, Kukovec, Tran. TLA+ Model Checking Made Symbolic. Proc. ACM Program. Lang. 3 (OOPSLA), art. 123, 2019. doi:10.1145/3360549 | Surnames, venue, DOI and summary. **TODO:** confirm first names | Apalache, a symbolic alternative to TLC |
| clarke1989 | Edmund M. Clarke, David E. Long, Kenneth L. McMillan. Compositional Model Checking. LICS 1989, pp. 353-362. doi:10.1109/LICS.1989.39190 | Details and summary | Compositional reasoning with interface processes |
| emerson1995 | E. Allen Emerson, Kedar S. Namjoshi. Reasoning About Rings. POPL 1995, pp. 85-94 | Details via reference lists; results via a survey | Cutoff results for token rings |
| hagen2025 | Martin Slind Hagen, Emil Lundqvist, Alex Phu, Yenan Wang, Kim Strandberg, Elad Michael Schiller. Towards a Formal Verification of Secure Vehicle Software Updates. Computers & Security, 2025, 104751. doi:10.1016/j.cose.2025.104751 | Abstract only | ProVerif-based security analysis of the UniSUF update framework |
| schmid2021 | Tobias Schmid, Stefanie Schraufstetter, Jonas Fritzsch, Dominik Hellhake, Greta Koelln, Stefan Wagner. Formal Verification of a Fail-Operational Automotive Driving System. arXiv:2101.07307 | Abstract only | Model checking used for automotive functional safety, on runtime fail-operational logic rather than updates |
| shoker2023 | Ali Shoker, Fernando Alves, Paulo Esteves-Verissimo. ScalOTA: Scalable Secure Over-the-Air Software Updates for Vehicles. arXiv:2307.02032 | Abstract only; no venue stated | OTA scalability and security |
| cirstea2024 | Cirstea, Kuppe, Loillier, Merz. Validating Traces of Distributed Programs Against TLA+ Specifications. arXiv:2404.16075 | Authors' surnames and summary. **TODO:** confirm first names and the final published venue | Checking implementation traces against TLA+ with TLC |
| howard2024 | Howard, Kuppe, Ashton, Chamayou, Crooks. Smart Casual Verification of CCF's Distributed Consensus and Consistency Protocols. arXiv:2406.17455 | Surnames and summary. **TODO:** confirm full names and NSDI 2025 | Linking TLA+ to an implementation through trace validation |

## B. Tools and artifacts

| Key | Item | Checked |
| --- | --- | --- |
| tlaplus | TLA+ tools, release v1.7.4 (TLC 2.19), tlaplus/tlaplus on GitHub | Release and SHA-256 recorded in `tools/versions.json` |
| mcuboot | MCUboot v2.4.0, commit `6d3b3d2c38ab20c242e5b9abb04d050086383eb2` | Pinned in `docs/MCUBOOT_VALIDATION_REPORT.md` |
| abfirmware | navadiashrey/ab-firmware-update-tla, GitHub. A single-device TLA+ model of power-loss-safe A/B update. Not peer-reviewed | Project description only |

## C. Not verified: must stay TODO in the paper

| Reference | What is missing |
| --- | --- |
| Lorch, Larraz, Tinelli, Chowdhury. A Comprehensive, Automated Security Analysis of the Uptane Automotive Over-the-Air Update Framework. RAID 2024, pp. 594-612. doi:10.1145/3678890.3678927 | Listed in index records, but the full text was not read, and one survey attributes this work to different authors. Closest formal OTA work, so **read it first** |
| Kuppusamy, Brown, Awwad, et al. Uptane: Securing Software Updates for Automobiles. escar 2016 | Full author list |
| Davis, Hirschhorn, Schvimer. eXtreme Modelling in Practice. PVLDB 13(9):1346-1358, 2020 | Seen only as a citation in other papers |
| Kirk, Nguyen, Bryans, Shaikh, et al. CSP formalisation of Uptane. QRS 2021; JLAMP 130, 2023 | Exact titles and authors |
| Boureanu, 2023. Uptane 2.0 in Tamarin | Seen only through a survey |
| AUTOSAR Adaptive UCM (doc 888) and Vehicle UCM (doc 1090), R24-11 and R25-11 | Normative rollback text was not read |
| AUTOSAR Explanation of Firmware Over-The-Air, R20-11 | Text not read; a search summary said rollback may need to reach dependent ECUs, which is unconfirmed |
| UN Regulation No. 156; ISO 24089:2023 | Primary text not read |
| "Trusted Verification of Over-the-Air (OTA) Secure Software..." NDSS AutoSec 2021 | Title and authors unconfirmed |
| DataMod 2024 paper on lifecycle verification gaps | Title and authors unconfirmed |
| "OTA Update Assurance for Energy and Charging Functions in SDVs" | ResearchGate listing only |
| Clarke, Grumberg, Long: abstraction and model checking | Not looked up. Probably the right citation for safety-preserving abstraction |
| Behrmann, David, Larsen: UPPAAL tutorial | Not found in search |
