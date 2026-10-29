#!/usr/bin/env python3
"""Generate a node-free Shadowrocket routing profile; phone validation required.

Python 3.9+. Keep this beside build_mihomo_routing.py. CC-BY-SA-4.0.
The profile uses public author examples, not a claim of an official format spec.
"""
import argparse
import json
from pathlib import Path
import re
from build_mihomo_routing import parse_ini, build, check_names, FOUR_REGIONS, FOUR_REGION_GROUPS


def make_shadowrocket(rules, groups, taiwan_present=False):
    validated = build(rules, groups, 86400)
    native_groups = {group['name']: group for group in validated['proxy-groups']}
    four_region_regex = '(?:' + '|'.join('(?:' + native_groups[name]['filter'] + ')' for name in FOUR_REGIONS) + ')'
    group_lines = []
    for raw in groups:
        name = raw['name']
        if name == '🇹🇼 台湾优先':
            continue
        group = native_groups[name]
        kind = group['type']
        refs = group.get('proxies', [])[:]
        regex = group.get('filter')
        if name in FOUR_REGION_GROUPS:
            # Shadowrocket author documentation discourages nested url-test groups.
            # The union preserves the same eligible exit nodes without nesting.
            refs, regex = [], four_region_regex
        if name == '🇨🇳 台湾节点':
            # Shadowrocket empty-group health behavior has not been phone-tested.
            # Generate the known nonempty branch instead of assuming Mihomo semantics.
            if taiwan_present:
                group = native_groups['🇹🇼 台湾优先']
                kind, refs, regex = 'url-test', [], group['filter']
            else:
                kind, refs, regex = 'fallback', ['🇯🇵 日本节点', '🇰🇷 韩国节点'], None
        if name == '🎥 奈飞节点':
            # No current nodes have NF tags; make the fallback explicit and unambiguous.
            kind, refs, regex = 'select', ['🚀 节点选择'], None
        items = [kind] + refs
        if kind in ('url-test', 'fallback'):
            items += ['url=' + group['url'], 'interval=' + str(group['interval']),
                      'timeout=5', 'select=0']
            if kind == 'url-test':
                items += ['tolerance=' + str(group['tolerance'])]
        elif refs:
            items += ['policy-select-name=' + refs[0]]
        if regex:
            re.compile(regex)
            if ',' in regex or '\n' in regex:
                raise ValueError('This emitter requires a comma-free single-line regex')
            items += ['policy-regex-filter=' + regex]
        group_lines.append(name + ' = ' + ','.join(items))
    rule_lines = []
    for rule in rules:
        source, policy = rule['source'], rule['policy']
        if source.startswith('https://'):
            rule_lines.append('RULE-SET,' + source + ',' + policy)
        else:
            # Shadowrocket uses FINAL. MATCH is the Mihomo spelling only.
            rule_lines.append(source[2:] + ',' + policy)
    assert len(group_lines) == len(groups) - 1 == 34
    assert len(rule_lines) == len(rules) == 39
    assert rule_lines[-1] == 'FINAL,🐟 漏网之鱼'
    header = '''# Shadowrocket independent routing profile. PHONE VALIDATION REQUIRED.
# No nodes, credentials, or subscription URL. Import your existing nodes separately.
# Source: https://github.com/ACL4SSR/ACL4SSR ; customizations: houxujiang.
# CC-BY-SA-4.0 https://creativecommons.org/licenses/by-sa/4.0/
# Uses native policy-regex-filter syntax shown by public Shadowrocket config authors.
# Does not assume Mihomo include-all-proxies or empty-fallback fields exist here.
# AI/Microsoft use the union of SG/US/JP/KR exit filters to avoid nested url-test groups.
# Current no-TW mode uses JP then KR; regenerate with --taiwan-present after adding TW.
# Netflix node selector uses the main node selector when no NF-tagged nodes exist.
# No DNS, MITM, scripts, rewrites, certificates, or subscription settings are supplied.
# Before connecting, check that AI/Microsoft contain only the intended 14 non-HK exits.

'''
    return header + '[Proxy Group]\n' + '\n'.join(group_lines) + '\n\n[Rule]\n' + '\n'.join(rule_lines) + '\n', validated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ini', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--check-subscription', type=Path)
    parser.add_argument('--taiwan-present', action='store_true',
                        help='Use real TW nodes. Required regeneration after adding a Taiwan exit.')
    args = parser.parse_args()
    rules, groups = parse_ini(args.ini.read_text(encoding='utf-8-sig'))
    profile, validated = make_shadowrocket(rules, groups, args.taiwan_present)
    assert 'policy-path=' not in profile and 'include-all-proxies=' not in profile
    assert not re.search(r'(?:vless|vmess|trojan|ss)://', profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(profile, encoding='utf-8')
    summary = {'profile': 'Shadowrocket routing only', 'groups': 34, 'rules': 39,
               'remote_rule_sets': 33, 'terminal_rule': 'FINAL',
               'ai_microsoft_candidates': 'SG/US/JP/KR exit-filter union, without nested url-test groups',
               'taiwan_policy': 'TW only' if args.taiwan_present else 'JP then KR fallback',
               'taiwan_regeneration_required_after_adding_TW': not args.taiwan_present,
               'netflix_fallback': 'main node selector', 'contains_nodes_or_subscription_url': False,
               'phone_validated': False, 'validation': 'generation and static checks only',
               'group_syntax_sources': [
                   'https://github.com/LOWERTOP/Shadowrocket/blob/main/lazy_group.conf#L166',
                   'https://github.com/LOWERTOP/Shadowrocket/blob/main/README.md#L937',
                   'https://github.com/Fromboy/Shadowrocket/blob/master/Shadowrocket-group.conf#L93'],
               'rule_syntax_source': 'https://github.com/LOWERTOP/Shadowrocket/blob/main/lazy_group.conf#L343'}
    if args.check_subscription:
        summary['local_name_classification'] = check_names(args.check_subscription, validated['proxy-groups'])
    if args.report:
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
