from dataclasses import dataclass
from rag_system.retrieval.router import RetrievalRouter
from rag_system.prompting.prompt_builder import PromptBuilder
from rag_system.llm.gemini_gemma import GemmaClient

@dataclass
class RAGResult:
    answer: str
    retrieved: list
    mode_used: str

class RAGPipeline:
    """
    Orchestrates: retrieval -> augmentation(prompt) -> generation
    """
    def __init__(self, router: RetrievalRouter, prompt_builder: PromptBuilder, llm: GemmaClient, settings):
        self.router = router
        self.pb = prompt_builder
        self.llm = llm
        self.s = settings

    def answer(self, query: str, mode: str) -> RAGResult:
        retrieved = self.router.retrieve(
            query=query,
            mode=mode,
            bm25_k=self.s.bm25_k,
            dense_k=self.s.dense_k,
            final_k=self.s.final_k,
            rrf_k=self.s.rrf_k,
            max_per_doc=self.s.max_per_doc,
        )
        prompt = self.pb.build_prompt(query, retrieved)
        text = self.llm.generate(
            prompt,
            temperature=self.s.temperature,
            max_output_tokens=self.s.max_output_tokens,
        )
        return RAGResult(answer=text, retrieved=retrieved, mode_used=mode)
