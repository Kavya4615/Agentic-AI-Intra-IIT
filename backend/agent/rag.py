"""
rag.py — Clinical Knowledge Base (RAG Retrieval)
==================================================
Loads clinical protocol text files from the knowledge base and retrieves
the most relevant protocols for a given patient scenario query.

Phase 9 update: retrieve() now returns BOTH protocol text AND the patient's
static clinical context block, formatted as a single prompt-ready string.

Uses keyword-based retrieval now; can be upgraded to pgvector + embeddings
by replacing the `retrieve_relevant_protocols` method.
"""

import os
from typing import List, Optional, Tuple

from agent.patient_context import PatientContext


# Maps scenario keywords -> protocol file names (without .txt)
SCENARIO_PROTOCOL_MAP = {
    "sepsis":              ["sepsis"],
    "gradual_deterioration": ["sepsis"],
    "deterioration":       ["sepsis"],
    "copd":                ["copd"],
    "copd_exacerbation":   ["copd"],
    "hemorrhagic_shock":   ["hemorrhagic_shock"],
    "hemorrhagic":         ["hemorrhagic_shock"],
    "shock":               ["hemorrhagic_shock"],
    "arrhythmia":          ["arrhythmia"],
    "intermittent_arrhythmia": ["arrhythmia"],
    "sudden_crisis":       ["sudden_crisis"],
    "pneumothorax":        ["sudden_crisis"],
    "crisis":              ["sudden_crisis"],
    "recovery":            ["sepsis"],  # post-op: general monitoring fallback
    "stable":              ["sepsis"],  # stable: general monitoring fallback
}


class ClinicalKnowledgeBase:
    """
    Loads clinical protocol text files from the local knowledge_base directory
    and provides keyword-based retrieval for relevant protocols given a scenario query.

    Phase 9: also accepts an optional PatientContext to include patient-specific
    clinical facts alongside the protocol text.

    To upgrade to semantic (vector) search:
      - Replace `_load_protocols` with an OpenAIEmbeddings + pgvector index build.
      - Replace `retrieve_relevant_protocols` with a similarity_search call.
    """

    def __init__(self, kb_path: str = "knowledge_base/protocols"):
        self.kb_path = kb_path
        self._protocols: dict = {}
        self._load_protocols()

    def _load_protocols(self):
        """Loads all .txt protocol files from the knowledge base directory."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, self.kb_path)

        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)
            return

        for filename in os.listdir(full_path):
            if filename.endswith(".txt"):
                key = filename[:-4]  # strip .txt
                filepath = os.path.join(full_path, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    self._protocols[key] = f.read()

        print(f"  [KnowledgeBase] Loaded {len(self._protocols)} protocols: {list(self._protocols.keys())}")

    def _match_protocol_keys(self, query: str) -> List[str]:
        """
        Match a query string against the scenario-protocol map.
        Returns a deduplicated list of protocol keys to retrieve.
        """
        query_lower = query.lower().replace(" ", "_")
        matched_keys = []

        # Direct map lookup (handles exact scenario names like 'copd_exacerbation')
        for keyword, protocol_keys in SCENARIO_PROTOCOL_MAP.items():
            if keyword in query_lower:
                for k in protocol_keys:
                    if k not in matched_keys:
                        matched_keys.append(k)

        # Fallback: check if the query directly contains any protocol file name
        if not matched_keys:
            for protocol_key in self._protocols:
                if protocol_key in query_lower:
                    matched_keys.append(protocol_key)

        return matched_keys

    def retrieve_relevant_protocols(self, query: str, max_protocols: int = 2) -> str:
        """
        Retrieve relevant clinical protocols for a given scenario query string.

        Parameters
        ----------
        query : str
            A scenario name or free-text description (e.g. 'sepsis deterioration').
        max_protocols : int
            Maximum number of protocols to include in the result.

        Returns
        -------
        str
            Concatenated protocol text(s) ready to inject into the LLM prompt.
        """
        matched_keys = self._match_protocol_keys(query)[:max_protocols]

        relevant_sections: List[str] = []
        for key in matched_keys:
            if key in self._protocols:
                relevant_sections.append(
                    f"--- PROTOCOL: {key.upper().replace('_', ' ')} ---\n{self._protocols[key]}"
                )

        if not relevant_sections:
            return (
                "No specific protocol found for this scenario. "
                "Apply general clinical deterioration guidelines: "
                "ensure airway, breathing, circulation; escalate to senior clinician."
            )

        return "\n\n".join(relevant_sections)

    def retrieve_with_context(
        self,
        query: str,
        patient_context: Optional[PatientContext] = None,
        max_protocols: int = 2,
    ) -> Tuple[str, List[str]]:
        """
        Phase 9: Retrieve protocols AND patient context together.

        Returns
        -------
        Tuple[str, List[str]]
            (combined_text_for_prompt, list_of_protocol_names_retrieved)

        The combined text has two clearly delineated sections:
          1. Patient-specific clinical context block
          2. Relevant clinical protocol(s)
        """
        # ── (a) Protocol retrieval ──────────────────────────────────────────
        matched_keys = self._match_protocol_keys(query)[:max_protocols]
        protocol_names: List[str] = []
        protocol_sections: List[str] = []

        for key in matched_keys:
            if key in self._protocols:
                protocol_names.append(key.upper().replace("_", " "))
                protocol_sections.append(
                    f"--- PROTOCOL: {key.upper().replace('_', ' ')} ---\n{self._protocols[key]}"
                )

        if not protocol_sections:
            protocol_text = (
                "No specific protocol found for this scenario. "
                "Apply general clinical deterioration guidelines: "
                "ensure airway, breathing, circulation; escalate to senior clinician."
            )
        else:
            protocol_text = "\n\n".join(protocol_sections)

        # ── (b) Patient context block ───────────────────────────────────────
        if patient_context:
            context_block = patient_context.to_structured_text()
        else:
            context_block = "No patient-specific context available."

        # ── (c) Combine ─────────────────────────────────────────────────────
        combined = (
            "=== PATIENT CLINICAL CONTEXT ===\n"
            f"{context_block}\n\n"
            "=== RELEVANT CLINICAL PROTOCOLS ===\n"
            f"{protocol_text}"
        )

        return combined, protocol_names

    def list_available_protocols(self) -> List[str]:
        """Return the names of all loaded protocols."""
        return list(self._protocols.keys())
