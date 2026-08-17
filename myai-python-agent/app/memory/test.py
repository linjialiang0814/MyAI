from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.embedding.volc_embedding import EmbeddingClient
from app.memory.mem_service import MemoryService


if __name__ == "__main__":
    service = MemoryService(embedding_client=EmbeddingClient(model="doubao-embedding-vision-250615"))
    user_id = "u2"

    samples = [
        #"My favorite programming language is Python",
        #"I like Python programming a lot",
        #"My major is computer science",
        #"My major is data science",
        #"I plan to apply for an internship this summer",
    ]

    #for s in samples:
        #result = service.process_user_input(user_id, s)
        #print(s, "->", result)

    print("\nRetrieved:")
    for item in service.retrieve_for_context(user_id, "What do I study and what do I like?"):
        print(item)

    #service.print_memories(user_id)