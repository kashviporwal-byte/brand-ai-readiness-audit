#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Skill 3: entity-semantics-audit
Covers:
- JSON-LD Organization / Product Schema auditing (F-ENT-001, F-ENT-002, F-ENT-003)
- sameAs Disambiguation checking (F-ENT-004, F-ENT-005)
- Quotable Definition matching & Subject Binding (F-ENT-006, F-ENT-007)
- Locale & Audience Grounding (F-ENT-009, F-ENT-011)
- FAQ & HowTo Schema Gap Detection (F-ENT-010)
"""

import sys
import os

# Add script directory to sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from run_entity_audit import audit_entity_semantics
from jsonld_schema_auditor import check_jsonld_schema
from sameas_disambiguator import check_sameas_disambiguation
from quotable_definition_checker import check_quotable_definition
from locale_audience_auditor import check_locale_audience, check_hreflang_reciprocity


def _has(findings, rule_id, severity=None):
    for f in findings:
        if f.get("id") == rule_id:
            if severity is None or f.get("severity") == severity:
                return True
    return False


def _ids(findings):
    return [f.get("id") for f in findings]


def run_tests():
    passed = 0
    failed = 0

    def check(name, condition, error_msg=""):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}: {error_msg}")
            failed += 1

    print("\n=== UNIT TESTS FOR SKILL 3 (entity-semantics-audit) ===")

    # 1. Clean page with complete Organization JSON-LD, sameAs, definition, locale → 0 findings
    clean_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Acme Corp - Enterprise Automation Platform</title>
    <meta name="description" content="Acme Corp is an enterprise workflow platform that automates cloud operations for 1,200 companies.">
    <meta property="og:site_name" content="Acme Corp">
    <meta name="geo.region" content="US-CA">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Acme Corp",
      "description": "Acme Corp provides automated enterprise workflow orchestration for Fortune 500 teams.",
      "url": "https://acme.example.com",
      "logo": "https://acme.example.com/logo.png",
      "inLanguage": "en-US",
      "audience": {
        "@type": "Audience",
        "audienceType": "Enterprise IT Teams"
      },
      "sameAs": [
        "https://www.wikidata.org/wiki/Q12345",
        "https://en.wikipedia.org/wiki/Acme_Corp"
      ]
    }
    </script>
</head>
<body>
    <main>
        <h1>Acme Corp Automation</h1>
        <p>Acme Corp is an enterprise workflow platform that connects distributed data pipelines in a single low-code environment.</p>
    </main>
</body>
</html>"""

    f1 = audit_entity_semantics(clean_html, "https://acme.example.com")
    check("clean_page_zero_critical_findings", not _has(f1, "F-ENT-001") and not _has(f1, "F-ENT-004"), f"got {_ids(f1)}")

    # 2. Missing Core Schema → F-ENT-001 High
    no_schema_html = """<!DOCTYPE html><html lang="en"><head><title>NoSchema Corp</title></head><body><h1>No Schema</h1></body></html>"""
    f2 = check_jsonld_schema(no_schema_html, "https://noschema.example.com")
    check("missing_core_schema_f_ent_001", _has(f2, "F-ENT-001", "high"), f"got {_ids(f2)}")

    # 3. Missing Critical Fields in Organization Schema → F-ENT-002 Medium
    incomplete_schema_html = """<!DOCTYPE html><html><head>
    <script type="application/ld+json">{"@type": "Organization", "name": "PartialCorp"}</script>
    </head><body></body></html>"""
    f3 = check_jsonld_schema(incomplete_schema_html, "https://partial.example.com")
    check("incomplete_schema_f_ent_002", _has(f3, "F-ENT-002", "medium"), f"got {_ids(f3)}")

    # 4. Malformed JSON-LD → F-ENT-003 High
    malformed_jsonld_html = """<!DOCTYPE html><html><head>
    <script type="application/ld+json">{"@type": "Organization", "name": "BadJsonCorp", }</script>
    </head><body></body></html>"""
    f4 = check_jsonld_schema(malformed_jsonld_html, "https://badjson.example.com")
    check("malformed_jsonld_f_ent_003", _has(f4, "F-ENT-003", "high"), f"got {_ids(f4)}")

    # 5. Zero sameAs links → F-ENT-004 High
    no_sameas_html = """<!DOCTYPE html><html><head>
    <script type="application/ld+json">{"@type": "Organization", "name": "NoSameAsCorp"}</script>
    </head><body></body></html>"""
    f5 = check_sameas_disambiguation(no_sameas_html, "https://nosameas.example.com")
    check("missing_sameas_f_ent_004", _has(f5, "F-ENT-004", "high"), f"got {_ids(f5)}")

    # 6. Social-only sameAs links → F-ENT-005 Medium
    social_sameas_html = """<!DOCTYPE html><html><head>
    <script type="application/ld+json">
    {"@type": "Organization", "name": "SocialCorp", "sameAs": ["https://twitter.com/socialcorp", "https://linkedin.com/company/socialcorp"]}
    </script>
    </head><body></body></html>"""
    f6 = check_sameas_disambiguation(social_sameas_html, "https://social.example.com")
    check("social_only_sameas_f_ent_005", _has(f6, "F-ENT-005", "medium"), f"got {_ids(f6)}")

    # 7. No quotable definition sentence → F-ENT-006 High
    no_def_html = """<!DOCTYPE html><html lang="en"><head><title>NoDef Corp</title></head>
    <body><main><h1>Welcome to our website</h1><p>Check out our products and contact us today.</p></main></body></html>"""
    f7 = check_quotable_definition(no_def_html, "https://nodef.example.com")
    check("missing_quotable_definition_f_ent_006", _has(f7, "F-ENT-006", "high"), f"got {_ids(f7)}")

    # 8. Jargon-heavy definition sentence → F-ENT-007 Medium
    jargon_def_html = """<!DOCTYPE html><html lang="en"><head><title>JargonCorp</title></head>
    <body><main><p>JargonCorp is an innovative, cutting-edge, revolutionary, game-changing enterprise platform that transforms businesses.</p></main></body></html>"""
    f8 = check_quotable_definition(jargon_def_html, "https://jargon.example.com")
    check("jargon_definition_f_ent_007", _has(f8, "F-ENT-007", "medium"), f"got {_ids(f8)}")

    # 9. Missing locale and audience grounding → F-ENT-009 Low
    no_locale_html = """<!DOCTYPE html><html><head><title>NoLocale</title></head><body></body></html>"""
    f9 = check_locale_audience(no_locale_html, "https://nolocale.example.com")
    check("missing_locale_f_ent_009", _has(f9, "F-ENT-009", "low"), f"got {_ids(f9)}")

    # 10. FAQ / HowTo Schema Gap on Q&A content with NO JSON-LD → F-ENT-010 Medium (Unconditional Check)
    faq_no_schema_html = """<!DOCTYPE html><html lang="en"><head><title>FAQ Page</title></head>
    <body><main>
        <h2>What is Acme Cloud?</h2>
        <p>Acme Cloud is a workflow platform.</p>
        <h2>How does Acme Cloud work?</h2>
        <p>It processes events in real time.</p>
    </main></body></html>"""
    f10 = check_jsonld_schema(faq_no_schema_html, "https://faq.example.com")
    check("faq_schema_gap_zero_schema_f_ent_010", _has(f10, "F-ENT-010", "medium"), f"got {_ids(f10)}")

    # 11. Hreflang Reciprocity Validation in multi-page mode → F-ENT-011 Medium
    crawled_pages = [
        {
            "url": "https://acme.example.com/en/",
            "raw_html": '<link rel="alternate" hreflang="es" href="https://acme.example.com/es/">'
        },
        {
            "url": "https://acme.example.com/es/",
            "raw_html": '<p>No hreflang backlink</p>'  # Missing reciprocal link back to /en/
        }
    ]
    f11 = check_hreflang_reciprocity(crawled_pages)
    check("hreflang_reciprocity_f_ent_011", _has(f11, "F-ENT-011", "medium"), f"got {_ids(f11)}")

    # 12. Orchestrator SiteContext interface test
    ctx = {"target_url": "https://acme.example.com", "raw_html": clean_html}
    f12 = audit_entity_semantics(ctx, "https://acme.example.com")
    check("orchestrator_site_context_interface", isinstance(f12, list), f"type is {type(f12)}")

    print(f"\nSkill 3 Battery: {passed}/{passed + failed} passed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
