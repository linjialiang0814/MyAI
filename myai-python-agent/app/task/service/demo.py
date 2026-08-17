from pprint import pprint

from app.task.service.prepare import build_task_service


if __name__ == "__main__":
    service = build_task_service()
    examples = [
        "check system info and cpu count",
        "请帮我计算 (23 + 7) * 4",
        "what time is it now in singapore",
        "统计这段文字的信息：Hello world from MyAI personal agent",
        "只是想打个招呼，不需要工具",
    ]

    for text in examples:
        print(f"\n>>> {text}")
        record = service.handle_task(text)
        pprint(record.model_dump())

#后续可能的改进方向：
#stats中增加更多能反馈工具调用的参数 例如：参数缺失率、validation的成功失败率， recovery成功率等
#toolplan中可以增加置信度、fallback到llm-based的统计等