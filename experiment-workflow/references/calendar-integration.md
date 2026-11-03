# 日历接入与实验待办

仅在首次安装、首次手动初始化、排期或事项更新时读取。所有远端操作由当前宿主已连接的插件或 MCP 执行；本地脚本负责待办、请求和真实工具收据，不内置任意厂商的网络凭据。

## 首次接入

安装返回 calendar.next_action 为 choose_calendar_and_connect 时：

1. 询问用户选择日历服务和具体目标日历。不能因当前会话可用某服务就固定它。
2. 使用宿主的插件发现或 MCP 配置能力，优先复用已有连接；缺少时安装或引导配置对应插件／MCP。需要登录、授权或宿主不支持自动安装时，明确显示实际待完成动作。
3. 用目标服务的真实工具读取日历列表，核对目标可写及 create/read/find/update 能力，不把支持名称当作连接成功。
4. 成功后把 provider、calendar_id、capabilities、time_zone 组成配置 JSON，调用 configure。项目只保存服务、日历和能力标识，认证留在宿主连接中。

```text
py -3.9 -B scripts/calendar_bridge.py --project <项目根> onboarding
py -3.9 -B scripts/calendar_bridge.py --project <项目根> configure --file <已核实连接.json>
```

配置 JSON 的 capabilities 是 `create/read/find/update` 字符串数组，time_zone 默认 Asia/Shanghai。其他 IANA 时区要求本机有可用时区数据；不可用时如实报告。不得把密码、token 或完整账户凭据加入配置。

## 排期与真实工具调用

每个后续阶段一条事项，正文集中列剩余步骤、待补信息、样品编号和实验记录位置，不创建待办.md。继续、再暂停或多次调用复用原 followup_id。

1. 阶段先保存。缺排期时集中问日期、开始时间和预计时长；已有内容不重问。排期 JSON 为 date（YYYY-MM-DD）、time（HH:MM）、minutes（正数）。
2. `prepare` 返回 needs_setup/needs_schedule/needs_review 时处理具体缺项；没有实际 dispatch 就不能写日历。返回 awaiting_receipt 时等待或补交原调用结果，不重复执行创建。
3. 只有 `status: dispatch` 时，宿主根据 request.operation、provider、calendar_id、payload，选择对应真实工具。create 请求含带时区的 start/end；update 有意省略时间，只改托管内容，保留用户手改排期。
4. 将真实返回规范化为收据，调用 receipt。tool_call_id 必须来自实际工具调用，不能填写虚构成功；失败或超时也提交对应失败收据。
5. 收据成功后再次 prepare，直到 synced 或出现明确待处理状态。未同步时不能宣称已创建或更新。

```text
py -3.9 -B scripts/calendar_bridge.py --project <项目根> prepare --experiment <编号> --followup <稳定ID> [--file <排期.json>]
py -3.9 -B scripts/calendar_bridge.py --project <项目根> receipt --experiment <编号> --followup <稳定ID> --file <真实返回规范化.json>
```

## 收据契约

共同字段为 request_id、tool_call_id、ok。失败另含 error。成功返回按操作区分：

| 操作 | 成功收据 | 要求 |
|---|---|---|
| find | lookup_complete: true、matches 数组 | 根据正文稳定标识查询；无法确定完整结果时保留不确定状态 |
| read | event；或 not_found: true | event.id 必须是请求对应事项 |
| create/update | event | 必须有真实 id、subject、body，并与本次请求回核 |

event 的 body 是规范化正文字符串，subject 为标题，可附 start/end 等服务返回。正文匹配标识为 `experiment-workflow:<followup_id>`。宿主应保留真实返回证据，不用请求内容假装服务已成功回写。

首次写入前先 find。创建响应丢失时提交失败收据，后续先 find：找到则绑定原事项，完整查询确认没有才允许创建；多条匹配必须核对。服务不具备可靠查询能力时不能盲目创建。

更新前 read，用户手改时间保留。完成标识作用于日历事项，不将计划改动视为实际实验执行；实际剩余内容完成后才标为已完成，并保留事项历史。远端删除返回待核对，不自动重建。

同步由会话调用推进，连接中断或离线时保存待同步状态，不宣称常驻后台同步或提醒服务已开启。首次连接与真实排期依用户选择执行，本项目测试仅使用模拟服务，不会为验收向真实日历写测试事项。
