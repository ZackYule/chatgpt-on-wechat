import json
import types
from bridge.context import Context
from bridge.reply import Reply
from channel.wechat.wechat_channel import WechatChannel
from channel.wechat.wechat_message import WechatMessage
from common.log import logger
import time
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import StreamingResponse
import asyncio
from app import run
from common.event_message_queue import event_message_queue
from contextlib import asynccontextmanager

# async def send_heartbeat(reply, context):
#     while True:
#         print('正在放入心跳事件...')
#         await event_message_queue.put(
#             {'data': {
#                 'reply': reply,
#                 'context': context
#             }})
#         print('✅ 放入心跳事件完成...')
#         await asyncio.sleep(1)  # 每60秒执行一次

# @asynccontextmanager
# async def start_heartbeat(app: FastAPI):
#     reply = "Heartbeat Reply"
#     context = "Heartbeat Context"
#     task = asyncio.create_task(send_heartbeat(reply, context))
#     yield
#     task.cancel()

# run()
# app = FastAPI(lifespan=start_heartbeat)

run()
app = FastAPI()


# 使用自定义的方法来序列化 Reply 对象
def reply_serializer(obj):
    if isinstance(obj, Reply):
        return {
            "type": obj.type.value if obj.type else None,
            "content": obj.content
        }
    elif isinstance(obj, Context):
        serialized_obj = {
            "type": obj.type.name if obj.type else None,
            "content": obj.content,
        }
        # Update the dictionary with key-value pairs from kwargs
        serialized_obj.update(obj.kwargs)
        return serialized_obj
    elif hasattr(obj, "__dict__"):
        return {
            k: v
            for k, v in obj.__dict__.items()
            if not callable(v) and not isinstance(v, types.FunctionType)
            and not isinstance(v, types.MappingProxyType)
        }
    else:
        raise TypeError(
            f"Object {obj} of type {obj.__class__.__name__} is not JSON serializable"
        )


async def event_generator():
    while True:
        print('正在取事件...')
        data = await event_message_queue.get()
        print('取得事件，正在发送...')
        print(data)
        print(type(data))
        res = json.dumps(data, default=reply_serializer)
        yield res
        await asyncio.sleep(1)


@app.post("/send")
async def handle_msg_endpoint(request: Request):
    if await request.body() == b"":
        raise HTTPException(status_code=401, detail="Empty request body")
    try:
        data = await request.json()
        msg = data.get('raw_message', None)
        print(msg)
    except json.JSONDecodeError:
        raise HTTPException(status_code=402, detail="Invalid JSON")

    try:
        cmsg = WechatMessage(msg, msg['IsGroup'])
    except NotImplementedError as e:
        logger.debug(f"[WX]group message {msg.MsgId} skipped: {e}")
        return {"message": "Group message skipped"}

    if msg['IsGroup']:
        WechatChannel().handle_group(cmsg)
    else:
        print('WechatChannel处理中')
        WechatChannel().handle_single(cmsg)

    return {"message": "Message processed successfully"}


@app.get("/events")
async def get_events():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
