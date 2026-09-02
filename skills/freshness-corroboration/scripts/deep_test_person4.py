"""
Deep Test Battery for Skill 4: freshness-corroboration (Spec-Corrected)
Validates all 3 subskills, corrected thresholds, false-positive resistance,
schema compliance, and adversarial edge cases.
Total: 24 comprehensive unit tests.
"""

import sys
import os
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from run_freshness_audit           import audit_freshness_corroboration
from temporal_freshness_checker    import check_temporal_freshness
from cross_web_corroborator        import (
    check_cross_web_corroboration,
    _parse_jsonld_claims,
    _extract_text_claims,
    _apply_two_source_consensus,
)
from information_density_evaluator import check_information_density


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ids(findings):
    return sorted(set(f["id"] for f in findings))

def _has(findings, rule_id, severity=None):
    for f in findings:
        if f["id"] == rule_id:
            if severity is None or f["severity"] == severity:
                return True
    return False

# Stub to skip live API calls in unit tests
_NO_API = {
    "skills.freshness-corroboration.scripts.cross_web_corroborator._wikidata_get_claims":
        lambda qid: {},
    "skills.freshness-corroboration.scripts.cross_web_corroborator._wikipedia_get_summary":
        lambda slug: {},
}

CURRENT_YEAR = datetime.now(timezone.utc).year


def run_unit_tests():
    results = []

    def check(name, condition, detail=""):
        ok = bool(condition)
        results.append({"test": name, "pass": ok, "detail": detail})
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
        return ok

    print("\n=== UNIT TESTS FOR SKILL 4 (freshness-corroboration — spec-corrected) ===")

    # ── 4.1 TEMPORAL FRESHNESS ────────────────────────────────────────────────

    # 1. No date metadata → F-FRSH-001 High
    no_date_html = """<!DOCTYPE html><html lang="en"><head><title>Acme</title></head>
    <body><main><h1>Acme Corp API Gateway</h1>
    <p>Acme Corp provides a high-performance API gateway routing millions of requests per second
    with sub-10ms latency, supporting REST, GraphQL, and gRPC protocols with OAuth 2.0 auth.
    Trusted by over 500 engineering teams globally for mission-critical traffic management.</p>
    </main></body></html>"""
    f1 = check_temporal_freshness(no_date_html)
    check("missing_date_metadata_f_frsh_001",
          _has(f1, "F-FRSH-001", "high"),
          f"expected F-FRSH-001 high; got {_ids(f1)}")

    # 2. Full dateModified in JSON-LD → NO F-FRSH-001
    dated_html = """<!DOCTYPE html><html lang="en"><head><title>Acme</title>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"WebPage",
     "datePublished":"2024-01-15T09:00:00Z","dateModified":"2025-08-20T12:00:00Z"}
    </script></head>
    <body><main><h1>Acme Platform</h1>
    <p>Enterprise API gateway processing 10 billion requests per day with AES-256 encryption,
    TLS 1.3, OAuth 2.0, and 40 global data centers. Founded 2018, San Francisco.</p></main>
    </body></html>"""
    f2 = check_temporal_freshness(dated_html)
    check("full_date_metadata_no_false_positive",
          not _has(f2, "F-FRSH-001"),
          f"fresh page must NOT trigger F-FRSH-001; got {_ids(f2)}")

    # 3. Copyright > 2 years out of date → F-FRSH-002 Medium (spec: only Medium)
    stale_year = CURRENT_YEAR - 3
    stale_copyright_html = f"""<!DOCTYPE html><html lang="en"><head><title>OldCorp</title>
    <meta property="article:modified_time" content="2025-06-01T00:00:00Z" />
    </head>
    <body><main><h1>OldCorp ERP System</h1>
    <p>OldCorp provides enterprise resource planning software for manufacturing.
    Our ERP supports inventory tracking, procurement, and finance across 200 factories
    in Europe and North America. REST API, LDAP integration, and SOC 2 certified.</p>
    </main><footer><p>Copyright © {stale_year} OldCorp Inc.</p></footer></body></html>"""
    f3 = check_temporal_freshness(stale_copyright_html)
    check("stale_copyright_3yr_f_frsh_002_medium",
          _has(f3, "F-FRSH-002", "medium"),
          f"3-year stale copyright must trigger F-FRSH-002 medium; got {[(x['id'],x['severity']) for x in f3]}")

    # 4. Copyright exactly 2 years old → NO finding (spec: > 2 years, not >= 2)
    two_years_copyright_html = f"""<!DOCTYPE html><html lang="en"><head><title>Corp</title>
    <meta property="article:modified_time" content="2025-06-01T00:00:00Z" />
    </head>
    <body><main><h1>Corp: Cloud Security Platform</h1>
    <p>Corp provides zero-trust network access for distributed engineering teams.
    Our ZTNA solution enforces RBAC policies across enterprise endpoints with 50ms auth latency.</p>
    </main><footer><p>© {CURRENT_YEAR - 2} Corp Inc.</p></footer></body></html>"""
    f4 = check_temporal_freshness(two_years_copyright_html)
    check("copyright_exactly_2yr_no_finding",
          not _has(f4, "F-FRSH-002"),
          f"exactly 2-year copyright must NOT trigger F-FRSH-002 (spec says > 2); got {_ids(f4)}")

    # 5. Current year copyright → NO F-FRSH-002
    current_html = f"""<!DOCTYPE html><html lang="en"><head><title>Fresh</title>
    <meta property="article:modified_time" content="2025-08-01T00:00:00Z" />
    </head>
    <body><main><h1>FreshCorp Monitoring</h1>
    <p>FreshCorp monitors cloud infrastructure across AWS, GCP, and Azure.
    Collects 100,000 metrics per second at 15-second resolution with p99 latency under 5ms.</p>
    </main><footer><p>© {CURRENT_YEAR} FreshCorp Inc.</p></footer></body></html>"""
    f5 = check_temporal_freshness(current_html)
    check("current_copyright_no_false_positive",
          not _has(f5, "F-FRSH-002"),
          f"current copyright must NOT trigger F-FRSH-002; got {_ids(f5)}")

    # 6. Future-dated timestamp → F-FRSH-003
    future_html = f"""<!DOCTYPE html><html lang="en"><head><title>Future</title>
    <meta property="article:modified_time" content="{CURRENT_YEAR + 2}-01-01T00:00:00Z" />
    </head>
    <body><main><h1>FutureCorp Analytics</h1>
    <p>FutureCorp provides predictive analytics processing 500 million events per hour
    with real-time demand forecasting, inventory optimization, and personalized pricing.
    Our ML pipeline uses XGBoost, LightGBM, and PyTorch models deployed on Kubernetes.
    REST API with OAuth 2.0. SDKs for Python, Java, and Go. SOC 2 Type II certified.
    Founded 2021 in Austin, TX. 150 employees across 3 offices. Series A: $30M.</p>
    </main></body></html>"""
    f6 = check_temporal_freshness(future_html)
    check("future_dated_timestamp_f_frsh_003",
          _has(f6, "F-FRSH-003"),
          f"future timestamp must trigger F-FRSH-003; got {_ids(f6)}")

    # 7. Non-ISO timestamp → F-FRSH-003
    bad_date_html = """<!DOCTYPE html><html lang="en"><head><title>Corp</title>
    <meta property="article:modified_time" content="June 15, 2025" />
    </head><body><main><h1>BadDate Corp Security</h1>
    <p>BadDate Corp provides zero-trust network access for distributed teams.
    ZTNA enforces RBAC across 3,000 enterprise endpoints with sub-50ms authentication
    and full audit logging via SIEM integrations. SOC 2 Type II certified.</p>
    </main></body></html>"""
    f7 = check_temporal_freshness(bad_date_html)
    check("malformed_timestamp_f_frsh_003",
          _has(f7, "F-FRSH-003"),
          f"non-ISO timestamp must trigger F-FRSH-003; got {_ids(f7)}")

    # 8. Thin page → no temporal findings
    f8 = check_temporal_freshness("<html><body><p>Hello world.</p></body></html>")
    check("thin_page_no_temporal_findings",
          len(f8) == 0,
          f"thin page must produce 0 findings; got {_ids(f8)}")

    # ── 4.2 CROSS-WEB CORROBORATION (unit tests skip live API calls) ──────────

    # 9. Page has specific claims + Wikidata/Wikipedia confirm same year → NO conflict finding
    #    (API stubs return matching founding year)
    well_grounded_html = """<!DOCTYPE html><html lang="en"><head><title>WellCorp</title>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","name":"WellCorp",
     "foundingDate":"2016","sameAs":["https://www.wikidata.org/wiki/Q123456",
     "https://en.wikipedia.org/wiki/WellCorp"]}
    </script></head>
    <body><main><h1>WellCorp Distributed Tracing</h1>
    <p>WellCorp was founded in 2016 in Seattle. Provides distributed tracing for microservices.
    Processes 1 trillion spans per month. Supports OpenTelemetry, Jaeger, and Zipkin.
    CEO: Alex Chen. Serving 2,000 enterprise customers globally. REST and gRPC APIs.</p>
    </main></body></html>"""

    # Stub APIs to return matching year → no conflict
    with patch("cross_web_corroborator._wikidata_get_claims",
               return_value={"founding_year": "2016", "ceo_name": "Alex Chen", "hq_city": "Seattle", "label": "WellCorp"}):
        with patch("cross_web_corroborator._wikipedia_get_summary",
                   return_value={"founding_year": "2016", "ceo_name": "Alex Chen", "hq_city": "Seattle", "summary": ""}):
            f9 = check_cross_web_corroboration(well_grounded_html, "https://wellcorp.com")
    check("matching_external_sources_no_conflict",
          not _has(f9, "F-FRSH-004"),
          f"matching Wikidata+Wikipedia must NOT trigger F-FRSH-004; got {_ids(f9)}")

    # 10. Both Wikidata AND Wikipedia contradict page founding year → F-FRSH-004 High
    conflict_html = """<!DOCTYPE html><html lang="en"><head><title>ClaimCorp</title>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","name":"ClaimCorp",
     "foundingDate":"2015","sameAs":["https://www.wikidata.org/wiki/Q987654",
     "https://en.wikipedia.org/wiki/ClaimCorp"]}
    </script></head>
    <body><main><h1>ClaimCorp Data Platform</h1>
    <p>ClaimCorp was founded in 2015 and serves over 50 million users globally.
    Present in 60 countries with 3,000 employees. CEO: Jane Smith. REST API, GraphQL.
    Enterprise security: SOC 2 Type II, ISO 27001. Founded 2015 in Austin, Texas.</p>
    </main></body></html>"""

    with patch("cross_web_corroborator._wikidata_get_claims",
               return_value={"founding_year": "2012", "ceo_name": "Jane Smith", "hq_city": "Austin", "label": "ClaimCorp"}):
        with patch("cross_web_corroborator._wikipedia_get_summary",
                   return_value={"founding_year": "2012", "ceo_name": "Jane Smith", "hq_city": "Austin", "summary": ""}):
            f10 = check_cross_web_corroboration(conflict_html, "https://claimcorp.com")
    check("two_source_founding_year_conflict_f_frsh_004",
          _has(f10, "F-FRSH-004", "high"),
          f"2-source conflict must trigger F-FRSH-004 high; got {[(x['id'],x['severity']) for x in f10]}")

    # 11. Only Wikidata contradicts (Wikipedia matches) → F-FRSH-005 Medium (single source)
    with patch("cross_web_corroborator._wikidata_get_claims",
               return_value={"founding_year": "2013", "ceo_name": None, "hq_city": None, "label": "ClaimCorp"}):
        with patch("cross_web_corroborator._wikipedia_get_summary",
                   return_value={"founding_year": "2015", "ceo_name": None, "hq_city": None, "summary": ""}):
            f11 = check_cross_web_corroboration(conflict_html, "https://claimcorp.com")
    check("single_source_conflict_f_frsh_005",
          _has(f11, "F-FRSH-005", "medium") and not _has(f11, "F-FRSH-004"),
          f"single-source conflict must trigger F-FRSH-005 medium only; got {[(x['id'],x['severity']) for x in f11]}")

    # 12. Pricing tiers mentioned but no prices → F-FRSH-005 advisory
    pricing_html = """<!DOCTYPE html><html lang="en"><head><title>PriceCorp</title></head>
    <body><main><h1>PriceCorp SaaS Platform</h1>
    <p>PriceCorp offers Free plan, Pro plan, and Enterprise plan for teams.
    Our Business edition includes advanced analytics and priority support.
    REST API, SSO, SOC 2 certified. Supports 500+ integrations. Founded 2019.
    Choose the right plan for your organization today. Upgrade anytime.</p>
    </main></body></html>"""
    with patch("cross_web_corroborator._wikidata_get_claims", return_value={}):
        with patch("cross_web_corroborator._wikipedia_get_summary", return_value={}):
            f12 = check_cross_web_corroboration(pricing_html, "https://pricecorp.com")
    check("pricing_tiers_no_values_f_frsh_005",
          _has(f12, "F-FRSH-005"),
          f"tier names without prices must trigger F-FRSH-005; got {_ids(f12)}")

    # 13. Pricing tiers WITH prices → NO pricing advisory
    priced_html = """<!DOCTYPE html><html lang="en"><head><title>PricedCorp</title></head>
    <body><main><h1>PricedCorp Platform</h1>
    <p>PricedCorp offers Free plan at $0/month, Pro plan at $25/month,
    and Enterprise plan from $500/month. Annual billing saves 20%.
    REST API, SOC 2 certified, 99.9% SLA. Founded 2019 in San Francisco.</p>
    </main></body></html>"""
    with patch("cross_web_corroborator._wikidata_get_claims", return_value={}):
        with patch("cross_web_corroborator._wikipedia_get_summary", return_value={}):
            f13 = check_cross_web_corroboration(priced_html, "https://pricedcorp.com")
    # Should NOT trigger the "tiers without values" finding
    has_pricing_advisory = any(
        f["id"] == "F-FRSH-005" and "pricing tier" in f["title"].lower()
        for f in f13
    )
    check("pricing_tiers_with_values_no_advisory",
          not has_pricing_advisory,
          f"tiers with prices must NOT trigger pricing advisory; got {_ids(f13)}")

    # 14. No claims, no sameAs, thin text → no corroboration findings
    vague_html = """<html><body><main>
    <h1>GenericCorp Solutions</h1>
    <p>We provide software solutions for businesses of all sizes.
    Our platform helps teams collaborate and achieve their goals efficiently.</p>
    </main></body></html>"""
    with patch("cross_web_corroborator._wikidata_get_claims", return_value={}):
        with patch("cross_web_corroborator._wikipedia_get_summary", return_value={}):
            f14 = check_cross_web_corroboration(vague_html, "https://generic.com")
    check("vague_page_no_false_positive",
          not _has(f14, "F-FRSH-004"),
          f"vague page must NOT trigger F-FRSH-004; got {_ids(f14)}")

    # ── 4.3 INFORMATION DENSITY — spec thresholds: High < 30%, Medium 30–45% ─

    # 15. Pure buzzword page → F-FRSH-006 High (density well below 30%)
    low_density_html = """<!DOCTYPE html><html lang="en"><head><title>FluffCorp</title></head>
    <body><main>
    <h1>FluffCorp: Revolutionary Next-Generation Platform</h1>
    <p>At FluffCorp, we are passionate about empowering enterprises to unleash their true potential
    through our groundbreaking, best-in-class, world-class revolutionary platform. Our next-generation,
    cutting-edge, state-of-the-art solutions drive paradigm shifts and enable seamless, frictionless
    synergy across your entire ecosystem. We leverage holistic end-to-end transformative innovation
    to disrupt traditional paradigms and unlock unprecedented value for visionary thought leaders
    and industry-leading innovators across the digital transformation landscape.</p>
    </main></body></html>"""
    f15 = check_information_density(low_density_html)
    check("low_density_high_buzzwords_f_frsh_006",
          _has(f15, "F-FRSH-006"),
          f"buzzword-heavy page must trigger F-FRSH-006; got {_ids(f15)}")

    # 16. Genuinely high-density technical page (density >= 45%) → NO F-FRSH-006
    # Every sentence is packed with numbers, proper technical acronyms, and verbs.
    # No marketing fluff at all. Target: > 45% density.
    high_density_html = """<!DOCTYPE html><html lang="en"><head><title>TechCorp</title></head>
    <body><main>
    <h1>TechCorp: Distributed Event Streaming</h1>
    <p>Ingestion: 10B events/day. Partitions: 1M per cluster. Replication: 3 AZs via Raft.
    Compression: LZ4, 4:1 ratio. p99 write: 4ms. p99 read: 2ms. Throughput: 1 GB/s/broker.
    Storage: LSM tree, WAL flushed every 100ms. Segment size: 1GB. Retention: configurable.
    Metrics: Prometheus endpoint at /metrics. Traces: OpenTelemetry OTLP gRPC port 4317.</p>
    <p>Auth: OAuth 2.0 PKCE. RBAC: 50 roles. Encryption: AES-256-GCM rest, TLS 1.3 transit.
    Certs: SOC 2 Type II, ISO 27001, PCI DSS Level 1, HIPAA BAA, FIPS 140-2.
    API: REST 200+ endpoints, gRPC proto3, OpenAPI 3.1 spec, HMAC-SHA256 webhooks.
    SDKs: Python 3.9+, Java 11+, Go 1.20+, Node.js 18+, Rust 1.70+, .NET 6+.
    Rate: 10,000 req/min/key. Quota reset: UTC midnight.</p>
    <p>Founded 2019 SF CA. Employees: 320, 8 offices, 5 countries.
    Series B: $85M. Customers: 2,400 incl 35 Fortune 500. ARR: $42M.</p>
    </main></body></html>"""
    f16 = check_information_density(high_density_html)
    check("high_density_page_no_f_frsh_006",
          not _has(f16, "F-FRSH-006"),
          f"high-density tech page must NOT trigger F-FRSH-006; got {_ids(f16)}")

    # 17. Medium-density page: mix of some technical + some filler → density 30–45%
    # Target: above 30% (not High) but below 45% (Medium severity).
    medium_density_html = """<!DOCTYPE html><html lang="en"><head><title>MedCorp</title></head>
    <body><main>
    <h1>MedCorp Cloud Storage</h1>
    <p>MedCorp provides object storage with AES-256 encryption and S3-compatible REST API.
    Plans: 1 TB at $10/month, 10 TB at $80/month, 100 TB enterprise at custom pricing.
    Available in AWS us-east-1, eu-west-1, and ap-southeast-1 regions. Founded 2020.
    Serves 500 companies in technology, finance, and healthcare sectors globally.
    99.99% durability SLA. Maximum object size: 5 TB. Minimum retention: 30 days.
    Supports multipart uploads, versioning, lifecycle policies, and cross-region replication.</p>
    <p>We believe teams deserve easy, reliable, and accessible storage without complexity.
    Our goal is to empower every organization to manage data effortlessly and grow confidently.</p>
    </main></body></html>"""
    f17 = check_information_density(medium_density_html)
    # Target: density is between 30% and 45%, so it should produce Medium severity (not High)
    check("medium_density_not_high_severity",
          not _has(f17, "F-FRSH-006", "high") and _has(f17, "F-FRSH-006", "medium"),
          f"medium-density page must produce Medium (not High) F-FRSH-006; got {[(x['id'],x.get('severity')) for x in f17]}")

    # 18. Excessive buzzword count → F-FRSH-007
    buzzword_heavy = """<!DOCTYPE html><html lang="en"><head><title>BuzzCorp</title></head>
    <body><main>
    <h1>BuzzCorp Solutions</h1>
    <p>BuzzCorp delivers revolutionary, next-generation, best-in-class solutions through seamless
    and frictionless innovation. Our world-class thought leadership empowers enterprises to unlock
    synergistic value. We leverage holistic, end-to-end digital transformation to disrupt paradigms
    and reimagine the future of work. Our cutting-edge, state-of-the-art technology stack enables
    game-changing outcomes. Our unparalleled, unmatched, unrivaled platform supercharges velocity.</p>
    </main></body></html>"""
    f18 = check_information_density(buzzword_heavy)
    check("buzzword_heavy_f_frsh_007",
          _has(f18, "F-FRSH-007"),
          f"buzzword-heavy page must trigger F-FRSH-007; got {_ids(f18)}")

    # 19. Thin page → no density findings
    f19 = check_information_density("<html><body><p>Short page. Contact us.</p></body></html>")
    check("thin_page_no_density_findings",
          len(f19) == 0,
          f"thin page must produce 0 density findings; got {_ids(f19)}")

    # ── INTERFACE & SCHEMA COMPLIANCE ─────────────────────────────────────────

    # 20. Empty string → empty list (no crash)
    check("empty_string_returns_empty",
          audit_freshness_corroboration("") == [],
          "empty string must return []")

    # 21. Empty dict → empty list
    check("empty_dict_returns_empty",
          audit_freshness_corroboration({}) == [],
          "empty dict must return []")

    # 22. Orchestrator SiteContext dict interface
    ctx = {"target_url": "https://test.com", "raw_html": no_date_html}
    f22 = audit_freshness_corroboration(ctx)
    check("orchestrator_site_context_interface",
          isinstance(f22, list),
          f"SiteContext dict must return a list; got {type(f22)}")

    # 23. All required finding keys present
    all_findings = audit_freshness_corroboration(no_date_html, "https://example.com")
    required = {"id", "skill_id", "title", "severity", "impact_area", "evidence", "suggested_action"}
    missing  = set()
    for f in all_findings:
        missing |= required - set(f.keys())
    check("finding_schema_keys",
          len(missing) == 0,
          f"missing keys: {missing}")

    # 24. severity enum compliance
    allowed = {"critical", "high", "medium", "low"}
    bad_sev = [f["severity"] for f in all_findings if f.get("severity") not in allowed]
    check("severity_enum_compliance",
          len(bad_sev) == 0,
          f"invalid severities: {bad_sev}")

    return results


def main():
    results = run_unit_tests()
    passed  = sum(1 for r in results if r["pass"])
    total   = len(results)

    print(f"\nSkill 4 Spec-Corrected Battery: {passed}/{total} passed")

    if passed < total:
        failed = [r["test"] for r in results if not r["pass"]]
        print("\nFAILED TESTS:")
        for t in failed:
            print(f"  - {t}")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
