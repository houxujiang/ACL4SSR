#!/usr/bin/env python3
"""Build a credential-free 3x-ui remote routing template from an ACL4SSR INI.

Python 3.9+; standard library only. This script never fetches subscriptions.
CC-BY-SA-4.0; adapted from ACL4SSR and houxujiang's Full.ini customizations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

AI_GROUP = "💬 OpenAi"
FOUR_REGIONS = ["🇸🇬 狮城节点", "🇺🇲 美国节点", "🇯🇵 日本节点", "🇰🇷 韩国节点"]
REGIONS = {
    "HK": "🇭🇰 香港节点", "JP": "🇯🇵 日本节点", "US": "🇺🇲 美国节点",
    "TW": "🇨🇳 台湾节点", "SG": "🇸🇬 狮城节点", "KR": "🇰🇷 韩国节点",
}
FOUR_REGION_GROUPS = [AI_GROUP, "Ⓜ️ 微软Bing", "Ⓜ️ 微软云盘", "Ⓜ️ 微软服务"]
UPSTREAM_PREFIX = "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/"


def parse_ini(text):
    rules, groups = [], []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith((";", "#", "[")):
            continue
        if line.startswith("ruleset="):
            policy, sep, source = line[len("ruleset="):].partition(",")
            if not sep:
                raise ValueError(f"Missing ruleset source at line {number}")
            rules.append({"policy": policy, "source": source})
        elif line.startswith("custom_proxy_group="):
            name, kind, *options = line[len("custom_proxy_group="):].split("`")
            groups.append({"name": name, "type": kind, "options": options})
    return rules, groups


def make_group(group):
    name, kind, options = group["name"], group["type"], group["options"]
    if kind not in ("select", "url-test", "fallback"):
        raise ValueError(f"Unsupported group type: {kind}")
    output = {"name": name, "type": kind}
    refs = [option[2:] for option in options if option.startswith("[]")]
    patterns = [option for option in options if option and not option.startswith(("[]", "http://", "https://"))]
    if kind in ("url-test", "fallback"):
        urls = [option for option in options if option.startswith(("http://", "https://"))]
        if len(urls) != 1:
            raise ValueError("Each health-check group requires exactly one test URL")
        time_option = options[-1]
        interval, _, tolerance = time_option.partition(",,")
        output.update({"url": urls[0], "interval": int(interval), "lazy": False, "expected-status": 204})
        if kind == "url-test":
            output["tolerance"] = int(tolerance or "50")
        patterns.remove(time_option)
    if refs:
        output["proxies"] = refs
    if patterns:
        if len(patterns) != 1:
            raise ValueError("Each dynamic group must have one regular expression")
        re.compile(patterns[0])
        output.update({"include-all-proxies": True, "filter": patterns[0], "empty-fallback": "REJECT"})
    if name == "🎥 奈飞节点":
        # Mihomo empty-fallback accepts a proxy, never another group.
        # Current self-hosted nodes have no NF/Netflix tag, so keep a usable group fallback.
        output["proxies"] = ["🚀 节点选择"]
    return output


def build(rules, groups, provider_interval):
    output_groups = [make_group(group) for group in groups]
    names = [group["name"] for group in output_groups]
    if len(set(names)) != len(names) or "PROXY" in names:
        raise ValueError("Duplicate group or attempted overwrite of the server's PROXY group")
    known = set(names) | {"DIRECT", "REJECT"}
    for group in output_groups:
        if not set(group.get("proxies", [])) <= known:
            raise ValueError("Unknown group reference")
        if group["name"] in FOUR_REGION_GROUPS:
            if group["type"] != "url-test" or group.get("proxies") != FOUR_REGIONS:
                raise ValueError("AI/Microsoft must retain exactly the four permitted exit regions")
    edges = {group["name"]: group.get("proxies", []) for group in output_groups}
    def visit(name, active, done):
        if name in active:
            raise ValueError("Proxy-group reference cycle")
        if name in done or name not in edges:
            return
        active.add(name)
        for ref in edges[name]:
            visit(ref, active, done)
        active.remove(name)
        done.add(name)
    done = set()
    for name in edges:
        visit(name, set(), done)
    providers, output_rules = {}, []
    for rule in rules:
        policy, source = rule["policy"], rule["source"]
        if policy not in known:
            raise ValueError("Ruleset refers to an undefined policy")
        if source.startswith("https://"):
            if not source.startswith(UPSTREAM_PREFIX) or urlsplit(source).query:
                raise ValueError("Only public upstream ACL4SSR list URLs may be published")
            basename = source.rsplit("/", 1)[-1]
            provider = "ACL4SSR_" + basename.removesuffix(".list")
            record = {"type": "http", "behavior": "classical", "format": "text", "url": source,
                      "path": f"./ruleset/acl4ssr/{basename}", "interval": provider_interval,
                      "proxy": "🚀 节点选择"}
            if provider in providers and providers[provider] != record:
                raise ValueError("Provider filename collision")
            providers[provider] = record
            output_rules.append(f"RULE-SET,{provider},{policy}")
        elif source.startswith("[]"):
            expression = source[2:]
            if expression == "FINAL":
                output_rules.append(f"MATCH,{policy}")
            else:
                output_rules.append(f"{expression},{policy}")
        else:
            raise ValueError("Unknown ruleset source syntax")
    if output_rules[-1] != "MATCH,🐟 漏网之鱼":
        raise ValueError("Final catch-all rule changed")
    ai_index = next(i for i, line in enumerate(output_rules) if line.startswith("RULE-SET,ACL4SSR_AI,"))
    for prefix in ("DOMAIN-SUFFIX,x.ai,✖️ 推特", "DOMAIN-SUFFIX,grok.com,✖️ 推特"):
        if output_rules.index(prefix) >= ai_index:
            raise ValueError("X/Grok exceptions must precede the upstream AI list")
    for provider in ("Google", "Bing", "OneDrive", "Microsoft"):
        if next(i for i, line in enumerate(output_rules) if line.startswith(f"RULE-SET,ACL4SSR_{provider},")) <= ai_index:
            raise ValueError("AI rules must precede broad Google/Microsoft rules")
    return {"proxy-groups": output_groups, "rule-providers": providers, "rules": output_rules}


def scalar(value):
    return json.dumps(value, ensure_ascii=False)


def yaml_lines(value, level=0):
    """Small deterministic YAML emitter; JSON quoting is used only for scalars."""
    indent = " " * level
    if isinstance(value, dict):
        for key, item in value.items():
            key = key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else scalar(key)
            if isinstance(item, (dict, list)):
                if not item:
                    yield f"{indent}{key}: {'{}' if isinstance(item, dict) else '[]'}"
                else:
                    yield f"{indent}{key}:"
                    yield from yaml_lines(item, level + 2)
            else:
                yield f"{indent}{key}: {scalar(item)}"
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                yield f"{indent}-"
                yield from yaml_lines(item, level + 2)
            else:
                yield f"{indent}- {scalar(item)}"


def check_names(path, groups):
    # Only fragments are processed from URI files; raw URIs and credentials are never returned.
    rows = path.read_text(encoding="utf-8-sig").splitlines()
    names = []
    for row in rows:
        row = row.strip()
        if not row or row.startswith("#"):
            continue
        if "://" in row:
            if "#" not in row:
                raise ValueError("Subscription contains a URI without a node-name fragment")
            names.append(unquote(row.rsplit("#", 1)[1]))
        else:
            names.append(row)
    by_name = {group["name"]: group for group in groups}
    counts = dict.fromkeys(REGIONS, 0)
    rejected = 0
    for name in names:
        matches = [code for code, group in REGIONS.items() if re.search(
            by_name["🇹🇼 台湾优先" if code == "TW" and "🇹🇼 台湾优先" in by_name else group]["filter"], name)]
        if len(matches) != 1:
            rejected += 1
        else:
            counts[matches[0]] += 1
    if rejected:
        raise ValueError(f"{rejected} node names have missing or overlapping exit classification; no names are logged")
    return {"node_count": len(names), "exit_counts": counts,
            "ai_microsoft_candidate_count": sum(counts[code] for code in ("SG", "US", "JP", "KR")),
            "ai_microsoft_hk_candidate_count": 0, "credential_data_written": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ini", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider-interval", type=int, default=86400)
    parser.add_argument("--check-subscription", type=Path)
    parser.add_argument("--model-output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    text = args.ini.read_text(encoding="utf-8-sig")
    rules, groups = parse_ini(text)
    config = build(rules, groups, args.provider_interval)
    report = {"target": "3x-ui v3.11.0 remote routing + Mihomo v1.19.31 or newer",
              "groups": len(config["proxy-groups"]), "providers": len(config["rule-providers"]),
              "rules": len(config["rules"]), "upstream_interval_seconds": args.provider_interval,
              "server_generated_proxies_preserved": True, "server_generated_PROXY_preserved": True,
              "contains_node_definitions": False, "contains_proxy_providers": False,
              "dynamic_empty_fallback": "REJECT", "netflix_default_fallback": "🚀 节点选择",
              "taiwan_policy": "first available TW, otherwise HK, otherwise JP", "group_graph_has_cycles": False}
    if args.check_subscription:
        report["local_subscription_check"] = check_names(args.check_subscription, config["proxy-groups"])
    header = ("# ACL4SSR routing only; no nodes, account IDs, credentials, or subscription URLs.\n"
              "# Source: https://github.com/ACL4SSR/ACL4SSR ; customizations: houxujiang.\n"
              "# CC-BY-SA-4.0 https://creativecommons.org/licenses/by-sa/4.0/\n"
              "# Target: 3x-ui v3.11.0 remote routing + Mihomo v1.19.31+.\n"
              "# Edit ACL4SSR_Online_Full.ini, then rebuild this generated file.\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(header + "\n".join(yaml_lines(config)) + "\n", encoding="utf-8")
    if args.model_output:
        args.model_output.write_text(json.dumps({"rules": rules, "groups": groups}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
