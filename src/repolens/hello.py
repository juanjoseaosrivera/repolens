"""Phase 0 deliverable: prove the LLM and embeddings pipes work end-to-end."""

from __future__ import annotations

from dotenv import load_dotenv

from repolens.embeddings import Embedder
from repolens.llm import LLM


def main() -> None:
    load_dotenv()

    text = "hello world"
    print(f"Embedding: {text!r}")
    [vector] = Embedder().embed([text])
    head = vector[:5]
    print(f"  vector dims: {len(vector)}")
    print(f"  first 5: {head}")

    print()
    print("Asking Claude to summarize those dimensions...")
    llm = LLM()
    formatted = ", ".join(f"{x:.6f}" for x in head)
    response = llm.complete(
        f"Here are the first 5 dimensions of an embedding vector for the string "
        f'"{text}": [{formatted}]. In one sentence, comment on what these floats '
        f"do (and don't) tell us in isolation."
    )
    print(f"  model: {response.model}")
    print(f"  tokens: in={response.input_tokens}, out={response.output_tokens}")
    print(f"  stop_reason: {response.stop_reason}")
    print()
    print(response.text)


if __name__ == "__main__":
    main()
