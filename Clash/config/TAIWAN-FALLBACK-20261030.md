# 台湾兜底与刷新机制（2026-10-30）

本文件记录台湾兜底方案及其独立验证结果，生成器与规则文件一同维护。

## 决策

Mihomo与INI增加“🇹🇼 台湾优先”候选辅助组，台湾主组按可用性依次选择：

1. 真实台湾候选；
2. 日本节点；
3. 韩国节点。

台湾→日本→韩国是用户明确指定的顺序，不再把香港作为台湾的兜底。日本、韩国组都只筛各自节点，不引用台湾主组，构建器另检查全图无循环。台湾候选为空时只含REJECT，主组跳过不可用候选继续日本/韩国；AI和微软四个组不包含台湾主组，因此仍只在SG/US/JP/KR四区的14个非香港出口中自动选择，没有加入DIRECT。兜底不代表能取得台湾地区授权。

Mihomo模板现在35组；最终原生订阅加上默认PROXY后共36组，另含33份规则提供者、39条规则。原有规则顺序未变。

Shadowrocket不能把Mihomo的empty-fallback直接照搬。因此当前独立conf保守保留34组，台湾直接为日本→韩国fallback；以后有真实台湾节点时，要给生成命令加 `--taiwan-present`，再更新手机配置。该分支会按台湾正则直接测速真实台湾候选。手机端的编译、候选发现和故障切换仍待验收，不宣称会在节点刷新时自动从日本分支切到台湾。

## 验证

- 构建器检查所有显式策略引用存在、没有循环、AI与三个微软组仍精确引用原四区。
- 当前15节点名称仍分类为HK1/JP1/SG1/US4/KR8/TW0；四个AI/微软组候选均为14，不含香港出口或DIRECT。
- 真实15节点与35组模板合并后，Mihomo v1.19.31配置测试返回0；公开摘要为 `mihomo-parse-validation.json`。
- 隔离启动Mihomo，使用本地HTTP 204服务及合成节点模拟三个场景：无TW选择JP；无TW且JP不可用选择KR；有可用TW选择TW。动态正则与显式成员展开两种模式的6项全部通过。REJECT-only候选确实被判为不可用，没有卡住主组。
- 运行报告为 `taiwan-runtime-validation.json`，复现脚本为 `verify_taiwan_fallback.py`。测试只证明组逻辑，未使用真实国家出口做地域解锁测试。所有临时核心进程已结束，系统代理及生产服务未改。
- 显式展开模式在Mihomo上验证通过，可供转换端复用该组结构；这不等于在旧Clash核心或Shadowrocket手机上实际验收。

## 三种更新要分开看

| 变化 | 什么会更新 | 需要做什么 |
| --- | --- | --- |
| ACL4SSR上游list更新 | Mihomo的33个rule-provider直接拉上游，当前间隔86400秒 | 可等待客户端provider更新或手动刷新；不必重建节点订阅 |
| fork中的分组/路由模板更新 | 3x-ui远程路由缓存10分钟，后台刷新并保留上一份有效配置 | 客户端刷新完整订阅；首次过期请求可能仍拿上一版，后台完成后再次刷新 |
| HK本机原生节点参数变化 | 原生订阅按当前DB生成；仅inbound settings共享缓存最多10秒，面板修改会立即清缓存，hosts每请求读取 | 修改保存后刷新客户端订阅；已经导入的旧节点不是实时推送更新 |
| HK聚合中的静态外链变化 | 当前11条kind=link记录只保存具体分享URI，不自动轮询其它VPS | 远端VPS改UUID、端口、host或传输参数后，先同步HK外链记录，再刷新客户端；只刷客户端不会修正旧静态URI |
| 聚合源真正使用kind=subscription | 3x-ui会从远程订阅地址取节点，缓存5分钟；失败时保留上次内容 | 远程源更新后等待缓存过期并刷新客户端；这与当前静态外链不是同一种模式 |
| 新增节点 | 仅同一subId下可订阅且启用的本机节点，或已经纳入HK的外链/远程订阅源会被聚合 | 必须先纳入HK聚合；在另一台VPS独立新增节点不会自动进入HK |
| Shadowrocket配置本身变化 | 独立conf与首页节点订阅分开管理 | 除更新节点外，还要更新/使用配置来刷新分组和远程规则；本地对配置的修改可能被远程配置更新覆盖 |

精确3x-ui v3.11.0源码依据：

- [本机settings缓存10秒与清除](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/settings_cache.go#L12)，[面板修改注册清除](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/service.go#L96)。
- [按请求读取inbounds和hosts](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/service.go#L738)，[subId与enable查询条件](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/service.go#L750)。
- [静态link与subscription分别展开](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/external_config.go#L83)，[远程订阅5分钟缓存](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/external_subscription.go#L18)。
- [远程路由10分钟缓存及后台刷新](https://github.com/MHSanaei/3x-ui/blob/v3.11.0/internal/sub/remote_routing.go#L36)。

当前“4个本机原生入口+11条静态外链”的来源结构沿用架构审计结果，本次没有打印私有源地址或UUID。Mihomo上游rule-provider的24小时间隔是本模板设置，不是3x-ui源码缓存；不要混为一个刷新周期。

