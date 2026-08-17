from app.context.context import ConversationContext

from app.memory.embedding.stub_embedding import StubEmbedding
from app.memory.embedding.volc_embedding import EmbeddingClient
from app.memory.retrieval.retriever_v1 import MemoryRetriever
from app.memory.store.in_mem_store_v1 import MemoryStore
from app.memory.maintenance.decay_v0 import MemoryDecay
from app.memory.retrieval.policy_v0 import MemoryPolicy
from app.memory.writer.rule_writer import MemoryWritePolicy
from app.prompt.prompt_builder_v0 import PromptBuilder
from app.model.stub_llm import StubLLM
from app.model.volc_llm import VolcengineLLM

from app.task.tool.tool_registry import ToolRegistry
from app.task.plan.planner import ToolPlanner
from app.task.plan.validation import ToolValidation
from app.task.plan.executor import ToolExecutor
from app.task.plan.recovery import RecoveryPlanner
from app.task.service.task_service import TaskService
from app.task.stats.statistics import PlannerStats
from app.task.tools.system_info import SystemInfoTool

import logging
logger = logging.getLogger("agent")
#两个数据结构 一个用来存内存 另一个用来取数判断

context_manager = ConversationContext()

embedding_model = StubEmbedding()
embedding_client = EmbeddingClient(model = "ep-20260125150855-ntrsd")
memory_store = MemoryStore()
memory_retriever = MemoryRetriever(memory_store)
memory_policy = MemoryPolicy()
memory_writer = MemoryWritePolicy()
memory_decay = MemoryDecay()

prompt_builder = PromptBuilder()
llm = VolcengineLLM(model_id="ep-20260121164815-fqzvn", temperature=0.7)
stub_llm = StubLLM()

tool_registry = ToolRegistry()
planner = ToolPlanner(tool_registry)
validator = ToolValidation(tool_registry)
executor = ToolExecutor(tool_registry)
rec_planner = RecoveryPlanner(tool_registry, planner, validator)
stats_planner = PlannerStats(tool_registry)
tool_registry.register(SystemInfoTool())
task_service = TaskService(rec_planner, executor, stats_planner)

def generate_reply(user_id: str, message: str) -> str:    #user id 与 message 是输入
    """
    完整对话流程：
    1. 记忆检索
    2. 记忆选择（Step 9）
    3. Prompt 构建
    4. 模型生成
    """

    #获取user的记忆
    memories = memory_store.get_all(user_id)

    #按每次调用，对记忆分数进行衰退
    memories = memory_decay.apply_decay(memories)
    memory_store.replace_all(user_id, memories)

    #记忆写入判断mem type
    memory_to_write = memory_writer.should_write_v2(message) #通过mem_writer 得到 mem type

    #获取embed向量
    embed_vec = embedding_model.embed(message) #通过embedding 得到vector
    #embed_vec = embedding_client.embed(message)

    #检索长期记忆
    raw_memories = memory_retriever.retrieve(user_id, embed_vec) #通过retrieve得到similarity

    #控制性筛选
    selected_memories = memory_policy.filter_memories(raw_memories) #policy筛选 在这里为不同type乘系数与衰减

    #在这一步判断工具使用情况
    #if 不用工具 构建最终prompt如下不变
    #if 用工具， 根据用工具的返回结构构建prompt（builder中新的函数）
    #plan = planner.plan(content=message)#改成recovery中的
    #plan = planner.plan(message, [])
    decision = task_service.handle_task(message)
    if not decision.plan:
        #构建最终 Prompt
        final_prompt = prompt_builder.build_prompt(
            message=message,
            context=context_manager.get_context(user_id),
            memories=selected_memories
        )
    else:
        final_prompt = prompt_builder.build_task_prompt(
            decision = decision
        )
        #增加了task_record类型的mem type
        memory_store.add(user_id = user_id, vector=None, content = decision.to_text(), mem_type="task_record")
        #logger.info(
        # f"[Planner Decision]"
        # f"plan = {plan.to_dict()}"
        # )

    #将本次消息信息写入内存
    if memory_to_write: #如果出现不写内存的情况怎么办？ 在后续写内存的步骤判断吧
        memory_store.add(
            user_id=user_id,
            content=message,
            vector=embed_vec,
            mem_type=memory_to_write.mem_type
        )

    #调用大语言模型，生成回复
    response = stub_llm.generate(final_prompt)
    #response = llm.generate(final_prompt)

    return response
