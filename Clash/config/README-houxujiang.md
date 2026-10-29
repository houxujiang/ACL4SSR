# houxujiang 的 ACL4SSR 完整分流

本配置基于 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR)，沿用 CC-BY-SA-4.0，保留 Google 服务细分、X/Grok 独立策略及 OpenAI/微软四区自动选择。2026-10-29 同步上游规则，合入 AI.list，保留五次个人修改。

## 配置文件

- `ACL4SSR_Online_Full.ini`：供支持该格式的订阅转换工具使用。
- `mihomo-routing.yaml`：只含策略组、规则提供者和规则，供 3x-ui 3.11.0 的远程 Clash 规则模板使用；不包含节点或任何访问凭据。
- `../../Tool/build_mihomo_routing.py`：由 INI 生成原生模板，Python 3.9+，无需第三方依赖。

```sh
python Tool/build_mihomo_routing.py --ini Clash/config/ACL4SSR_Online_Full.ini --output Clash/config/mihomo-routing.yaml
```

编辑 INI 后重新生成并一并提交 YAML。3x-ui 配置 `subClashEnableRouting=true`、`subClashRules=<模板HTTPS地址>`，保留服务端生成的节点。远程公开规则列表由客户端定期获取，保持上游更新。

## 个人策略

- Google FCM、GoogleCN、Play 下载、Play 服务、Google、YouTube 分开控制。
- x.ai、grok.com 和 Twitter/X 使用原来的“推特”策略，优先于 AI 总表。
- “OpenAi”包含上游新增 AI 域名；OpenAI 和三个微软策略只在新加坡、美国、日本、韩国出口间测速，不加入香港、台湾或 DIRECT。
- 自建 `xuiAABB` 节点按最终出口归类；例如 `xuihkusa` 属于美国出口，`xuitkskr` 属于韩国出口。
- 无台湾节点时，该区域明确拒绝；没有 Netflix 标签节点时，“奈飞节点”保留“节点选择”兜底。

原生 YAML 面向 Mihomo 1.19.31+，使用动态分组及 text rule-provider。旧 Clash 内核不能直接视为兼容，Clash for Windows 应使用对应的 Mihomo 内核。Shadowrocket 的节点订阅和分流配置分别管理；不要把原生 YAML 的所有 Mihomo 字段当作跨客户端规范。

这里公开的只有规则和构建代码。节点、UUID、密钥、订阅地址及服务账号配置均不应提交到本仓库。
