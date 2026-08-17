from app.context.context import ConversationContext
from app.model.stub_llm import StubLLM
from app.model.volc_llm import VolcengineLLM
from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.embedding.volc_embedding import EmbeddingClient
from app.memory.store.in_mem_store_v0 import MemoryStore
from app.memory.retrieval.retriever_v0 import MemoryRetriever
from app.memory.retrieval.policy_v0 import MemoryPolicy
from app.prompt.prompt_builder_v0 import PromptBuilder

#service after Step 8
stub_llm = StubLLM()
llm = VolcengineLLM(
    model_id="ep-20260121164815-fqzvn",
    temperature=0.7
)

#短期上下文
context_manager = ConversationContext(max_turns = 6)

#长期记忆组件
stub_embedding = StubEmbedding()
embedding_client = EmbeddingClient(
    model = "ep-20260125150855-ntrsd"
)
memory_store = MemoryStore()
memory_retriever = MemoryRetriever(top_k = 5)
memory_policy = MemoryPolicy()
prompt_builder = PromptBuilder()

def generate_reply(user_id:str, message:str) -> str:
    """当前无模型"""

    #短期上下文
    context_manager.add_message(user_id, f"User:{message}")
    short_context = context_manager.get_context(user_id)

    #长期记忆组件 存储、检索
    msg_vector = stub_embedding.embed(message)
    #msg_vector = embedding_client.embed(message)

    vectors, texts = memory_store.get_user_memory(user_id)
    retrieved = memory_retriever.retrieve_v1(msg_vector, vectors, texts)

    memory_store.add(user_id, msg_vector, message)

    retrieved_texts = "\n".join(
        [f"-{text}(score = {score:.2f})" for text, score in retrieved]
    )#后续再考虑怎样编写进prompt

    #selected_memories = memory_policy.filter_memories(retrieved)

    #prompt = prompt_builder.build_prompt(message, retrieved_texts)
    #prompt = (f"{message}")
    #reply = llm.generate(prompt)
    prompt = f"""
            You are a personal AI assistant.
            [Conversation]
            {short_context}
            
            [Retrieved texts]
            {retrieved_texts}
    
            [User]
            {message}
        """.strip()
    reply = prompt

    context_manager.add_message(user_id, f"Agent:{reply}")

    return reply
    #return f"Python received: {message} from user: {user_id}"


