# Inherited Taint

**How Legacy Health Systems Poison AI Agents, and How to Unlearn the Damage**

Hospitals are connecting AI agents to systems that are decades old: HL7 v2 messages between laboratory and record systems, DICOM headers in imaging archives, scanned faxes turned into text by OCR. Their free-text fields reach the agent as trusted internal data. Whatever enters a legacy system, by error or by attack, is passed on with the authority of the hospital's own records. The agent may act on it, write it into a summary or its memory, and send it to other agents.

This project studies that *inherited taint*:

1. **Propagation:** how far an instruction hidden in a legacy field travels through collaborating agents, and which legacy channels are most dangerous.
2. **Taint tracking and detection:** carrying each piece of data's source and trust level through the agent pipeline, so that instructions from untrusted fields are never followed.
3. **Unlearning:** removing the taint, and everything derived from it, from agent memory and from models, including federated models trained across hospitals.

> **Status: planned, prototype in progress.** All experiments will use synthetic patients and synthetic HL7 v2, FHIR and DICOM data, with agent pipelines built for this project. No real patient data and no real hospital systems are used.

Builds on [Poisoned Papers](https://github.com/Zubair-DLCS/Poisoned-Papers) (prompt-injection attacks on screening agents) and [Camouflaged Instructions](https://github.com/Zubair-DLCS/Camouflaged-Instructions) (detecting engineered instructions in odd text).

## Author

**Malak Zubair**, Assistant Professor of Computer Science, G.C.M.S Timergara, Khyber Pakhtunkhwa, Pakistan. GitHub: [Zubair-DLCS](https://github.com/Zubair-DLCS)
