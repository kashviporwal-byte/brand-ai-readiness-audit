"""
Deep Test Battery for Skill 5: engagement-ux-audit
Validates all 4 subskills, 8 failure modes, false-positive resistance,
Flesch calculation accuracy, schema compliance, and adversarial edge cases.
Total: 20 comprehensive unit tests.
"""

import sys
import os
import json
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from run_engagement_audit import audit_engagement_ux
from heading_anchor_auditor import check_heading_anchors
from viewport_clarity_checker import check_viewport_clarity
from interstitial_friction_detector import check_interstitial_friction
from readability_cognitive_scorer import check_cognitive_readability, calculate_flesch_reading_ease


def run_unit_tests():
    results = []

    def check(name, condition, detail=""):
        ok = bool(condition)
        results.append({"test": name, "pass": ok, "detail": detail})
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
        return ok

    print("\n=== UNIT TESTS FOR SKILL 5 (engagement-ux-audit) ===")

    # 1. Clean, fully-optimized page -> MUST produce 0 findings (Zero False Positives)
    clean_html = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Apex: Real-Time Event Bus</title></head>
    <body>
      <header class="hero">
        <h1>Apex Cloud: Real-Time Event Stream Broker</h1>
        <p class="hero-subhead">Stream millions of events with sub-millisecond latency and guaranteed order.</p>
        <a href="/signup" class="btn btn-primary">Start Free Trial</a>
      </header>
      <main>
        <h2 id="architecture-overview">Architecture Overview</h2>
        <p>Apex uses a distributed append-only log architecture. Each broker node operates independently.</p>
        <ul>
          <li><strong>Zero garbage collection:</strong> Off-heap memory pooling.</li>
          <li><strong>End-to-end encryption:</strong> TLS 1.3 encryption at rest and in transit.</li>
        </ul>
        <h2 id="latency-benchmarks">Latency Benchmarks</h2>
        <p>Our benchmark shows consistent 4x lower latency compared to legacy queue solutions under peak load.</p>
        <h3 id="benchmark-methodology">Benchmark Methodology</h3>
        <p>We tested 50,000 requests per second across three availability zones.</p>
      </main>
    </body>
    </html>"""

    clean_findings = audit_engagement_ux(clean_html, "https://apex.io")
    check(
        "clean_page_zero_false_positives",
        len(clean_findings) == 0,
        f"clean page should have 0 findings; got {len(clean_findings)}: {[f['id'] for f in clean_findings]}"
    )

    # 2. Missing heading anchor IDs -> F-ENG-001
    missing_anchors_html = """<html><body>
    <header><h1>Real-Time Database Platform</h1><a href="/signup" class="btn">Sign Up</a></header>
    <main>
      <h2>Performance Overview</h2><p>Fast database performance.</p>
      <h2>Storage Engines</h2><p>LSM tree storage architecture.</p>
      <h2>Replication Protocol</h2><p>Raft consensus across regions.</p>
      <h3>Fault Tolerance</h3><p>Automatic failover under 200ms.</p>
    </main></body></html>"""
    f1 = check_heading_anchors(missing_anchors_html)
    check(
        "missing_heading_anchors_f_eng_001",
        any(f["id"] == "F-ENG-001" and f["severity"] == "high" for f in f1),
        f"expected F-ENG-001; got {[f['id'] for f in f1]}"
    )

    # 3. Duplicate and generic anchor IDs -> F-ENG-002
    dup_anchors_html = """<html><body>
    <header><h1>Analytics Platform</h1><a href="/signup" class="btn">Sign Up</a></header>
    <main>
      <h2 id="section">Overview</h2><p>Intro text.</p>
      <h2 id="section">Features</h2><p>Feature text.</p>
      <h3 id="item">Detail</h3><p>Detail text.</p>
    </main></body></html>"""
    f2 = check_heading_anchors(dup_anchors_html)
    check(
        "duplicate_and_generic_anchor_ids_f_eng_002",
        any(f["id"] == "F-ENG-002" and f["severity"] == "medium" for f in f2),
        f"expected F-ENG-002; got {[f['id'] for f in f2]}"
    )

    # 4. Dead fragment links -> F-ENG-008
    dead_links_html = """<html><body>
    <header><h1>Dashboard</h1><a href="/signup" class="btn">Sign Up</a></header>
    <h2 id="one">One</h2><h2 id="two">Two</h2>
    <a href="#">Link 1</a>
    <a href="#">Link 2</a>
    <a href="#top">Link 3</a>
    </body></html>"""
    f8 = check_heading_anchors(dead_links_html)
    check(
        "dead_fragment_links_f_eng_008",
        any(f["id"] == "F-ENG-008" and f["severity"] == "low" for f in f8),
        f"expected F-ENG-008; got {[f['id'] for f in f8]}"
    )

    # 5. Vague slogan & missing CTA -> F-ENG-003, F-ENG-004
    vague_hero_html = """<html><body>
    <header class="hero">
      <h1>Unleash Tomorrow</h1>
      <p>The future of innovation.</p>
    </header>
    <main><h2 id="a">A</h2><p>Some text.</p></main>
    </body></html>"""
    f_vp = check_viewport_clarity(vague_hero_html)
    check(
        "vague_slogan_f_eng_003",
        any(f["id"] == "F-ENG-003" and f["severity"] == "high" for f in f_vp),
        f"expected F-ENG-003; got {[f['id'] for f in f_vp]}"
    )
    check(
        "missing_cta_f_eng_004",
        any(f["id"] == "F-ENG-004" and f["severity"] == "medium" for f in f_vp),
        f"expected F-ENG-004; got {[f['id'] for f in f_vp]}"
    )

    # 6. Intrusive blocking modal -> F-ENG-005
    modal_html = """<html><body>
    <div class="overlay newsletter-popup" style="position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:9999;">
      <h2>Subscribe to our newsletter</h2>
      <input type="email" placeholder="Email"><button>Submit</button>
    </div>
    <main><h1>Normal Site</h1><p>Normal text.</p></main>
    </body></html>"""
    f_mod = check_interstitial_friction(modal_html)
    check(
        "intrusive_modal_f_eng_005",
        any(f["id"] == "F-ENG-005" and f["severity"] == "high" for f in f_mod),
        f"expected F-ENG-005; got {[f['id'] for f in f_mod]}"
    )

    # 7. High cognitive load (Flesch < 25, avg sentence > 18) -> F-ENG-006
    academic_text = (
        "The epistemological underpinnings of polymorphic multidimensional semantic topologies "
        "necessitate the operationalization of heterogeneous architectural invariants across distributed "
        "computational substrates to mitigate non-deterministic synchronization latencies. "
        "Furthermore, the phenomenological characterization of asynchronous transactional serialization "
        "imposes substantial computational overhead upon multi-tenant relational persistence layers, "
        "thereby exacerbating throughput degradation in hyperscale distributed infrastructure clusters. "
        "Consequently, empirical investigations demonstrate that traditional optimistic concurrency controls "
        "exhibit sub-optimal fault recovery profiles under high contention workloads. "
        "Additionally, the institutionalization of decentralized consensus protocols across adversarial "
        "Byzantine environments requires the continuous verification of cryptographically signed state transitions, "
        "substantially amplifying algorithmic complexity and inter-node communication latency."
    )
    academic_html = f"<html><body><header><h1>Whitepaper</h1><a href='/' class='btn'>Download</a></header><main><p>{academic_text}</p></main></body></html>"
    f_read = check_cognitive_readability(academic_html)
    flesch, words, sentences, avg_len = calculate_flesch_reading_ease(academic_text)
    check(
        "high_cognitive_load_f_eng_006",
        any(f["id"] == "F-ENG-006" for f in f_read),
        f"academic text (Flesch={flesch}, avg_len={avg_len}) should flag F-ENG-006; got {[f['id'] for f in f_read]}"
    )

    # 8. Unscannable wall of text (> 400 words, no bullets, no bold) -> F-ENG-007
    wall_of_text = "Word " * 450
    wall_html = f"<html><body><header><h1>Article</h1><a href='/' class='btn'>Next</a></header><main><p>{wall_of_text}</p></main></body></html>"
    f_wall = check_cognitive_readability(wall_html)
    check(
        "unscannable_wall_of_text_f_eng_007",
        any(f["id"] == "F-ENG-007" and f["severity"] == "low" for f in f_wall),
        f"wall of text should flag F-ENG-007; got {[f['id'] for f in f_wall]}"
    )

    # 9. Empty inputs handling
    check("empty_html_returns_empty", audit_engagement_ux("") == [], "empty string returns []")
    check("empty_dict_returns_empty", audit_engagement_ux({}) == [], "empty dict returns []")

    # 10. SiteContext dict interface
    ctx = {
        "target_url": "https://example.com",
        "raw_html": clean_html
    }
    ctx_findings = audit_engagement_ux(ctx)
    check(
        "orchestrator_site_context_interface",
        isinstance(ctx_findings, list),
        f"SiteContext dict returns list (length {len(ctx_findings)})"
    )

    # 11. Schema compliance
    sample = audit_engagement_ux(vague_hero_html, "https://test.com")
    if sample:
        f0 = sample[0]
        required_keys = {"id", "skill_id", "title", "severity", "impact_area", "evidence", "suggested_action"}
        check(
            "finding_schema_keys",
            required_keys.issubset(f0.keys()),
            f"missing keys: {required_keys - set(f0.keys())}"
        )
        sa_keys = {"summary", "priority", "rationale", "code_fix_example"}
        check(
            "suggested_action_schema_keys",
            sa_keys.issubset(f0.get("suggested_action", {}).keys()),
            f"missing suggested_action keys: {sa_keys - set(f0.get('suggested_action', {}).keys())}"
        )

    # =========================================================================
    # CLAUDE ADVERSARIAL REAL-WORLD PROBE SUITE (Probes 12 - 17)
    # =========================================================================
    print("\n=== CLAUDE ADVERSARIAL EDGE-CASE PROBES ===")

    # 12. Adversarial Probe: Footer-only CTA must NOT satisfy hero CTA requirement (Bug 1 regression)
    footer_cta_html = """<!DOCTYPE html><html><body>
    <header class="hero">
      <h1>Stripe Payments: Global Payment Infrastructure</h1>
      <p>Accept payments and scale without borders across 190+ countries.</p>
    </header>
    <main><h2 id="features">Features</h2><p>Scalable APIs.</p></main>
    <footer>
      <p>Ready to build?</p>
      <a href="/signup" class="btn cta-action">Sign Up in Footer</a>
    </footer>
    </body></html>"""
    f_footer_cta = check_viewport_clarity(footer_cta_html)
    check(
        "adversarial_footer_cta_not_counted_as_hero",
        any(f["id"] == "F-ENG-004" for f in f_footer_cta),
        f"footer-only CTA should trigger F-ENG-004; got {[f['id'] for f in f_footer_cta]}"
    )

    # 13. Adversarial Probe: Nav links must NOT satisfy hero CTA or hero headline (Bug 1 regression)
    nav_fake_hero_html = """<!DOCTYPE html><html><body>
    <nav class="top-nav">
      <a href="/docs" class="btn">Docs</a>
    </nav>
    <header>
      <h1>Home</h1>
    </header>
    <main><h2 id="intro">Intro</h2><p>Some text.</p></main>
    </body></html>"""
    f_nav_fake = check_viewport_clarity(nav_fake_hero_html)
    check(
        "adversarial_nav_not_counted_as_hero_cta",
        any(f["id"] == "F-ENG-003" for f in f_nav_fake) and any(f["id"] == "F-ENG-004" for f in f_nav_fake),
        f"nav chrome must not mask vague H1 or missing hero CTA; got {[f['id'] for f in f_nav_fake]}"
    )

    # 14. Adversarial Probe: Numbered generic IDs like section-1, content-2 (Bug 2 regression)
    numbered_generic_html = """<!DOCTYPE html><html><body>
    <header><h1>Cloud Analytics</h1><a href="/try" class="btn">Try</a></header>
    <main>
      <h2 id="section-1">Overview</h2><p>P1</p>
      <h2 id="section-2">Architecture</h2><p>P2</p>
      <h3 id="content-2">Deep Dive</h3><p>P3</p>
    </main>
    </body></html>"""
    f_numbered = check_heading_anchors(numbered_generic_html)
    check(
        "adversarial_numbered_generic_ids_caught",
        any(f["id"] == "F-ENG-002" for f in f_numbered),
        f"numbered generic IDs (section-1, content-2) must trigger F-ENG-002; got {[f['id'] for f in f_numbered]}"
    )

    # 15. Adversarial Probe: Docs site with sidebar nav headings must NOT produce false positive (Bug 3 regression)
    docs_sidebar_html = """<!DOCTYPE html><html><body>
    <header><h1>Platform Documentation</h1><a href="/docs" class="btn">Docs</a></header>
    <aside class="sidebar">
      <nav>
        <h3>Getting Started</h3>
        <h3>API Reference</h3>
        <h3>Webhooks</h3>
      </nav>
    </aside>
    <main>
      <h2 id="create-payment">Create a Payment</h2><p>Code sample.</p>
      <h2 id="refund-charge">Refund a Charge</h2><p>Code sample.</p>
      <h2 id="listen-events">Listen to Events</h2><p>Code sample.</p>
    </main>
    </body></html>"""
    f_docs_sidebar = check_heading_anchors(docs_sidebar_html)
    check(
        "adversarial_sidebar_nav_headings_excluded",
        len(f_docs_sidebar) == 0,
        f"sidebar nav headings must not dilute content ratio; got {[f['id'] for f in f_docs_sidebar]}"
    )

    # 16. Adversarial Probe: Compound hyphenated modal keywords (cookie-wall, email-capture) (Bug 4 regression)
    compound_modal_html = """<!DOCTYPE html><html><body>
    <div class="cookie-wall email-capture-gate">
      <h2>Cookie Consent & Newsletter Gate</h2>
      <p>You must accept to view this page.</p>
    </div>
    <div class="paywall-gate">Blocked.</div>
    <main><h1>Site</h1><p>Text.</p></main>
    </body></html>"""
    f_compound_modal = check_interstitial_friction(compound_modal_html)
    check(
        "adversarial_compound_modal_keywords_caught",
        any(f["id"] == "F-ENG-005" for f in f_compound_modal),
        f"compound keywords (cookie-wall, email-capture-gate) must trigger F-ENG-005; got {[f['id'] for f in f_compound_modal]}"
    )

    # 17. Adversarial Probe: Dormant modal (display:none exit-intent) must NOT false-positive (Second-order safety)
    dormant_modal_html = """<!DOCTYPE html><html><body>
    <!-- Dormant exit-intent modal: hidden on initial page load -->
    <div class="newsletter-popup" style="display:none;">
      <h2>Sign up for updates</h2>
    </div>
    <div class="cookie-wall-banner" style="display: none;">
      <p>Cookies info.</p>
    </div>
    <header class="hero">
      <h1>Cloud Database: Sub-millisecond Storage Engine</h1>
      <a href="/start" class="btn btn-primary">Get Started</a>
    </header>
    <main><h2 id="features">Features</h2><p>High speed.</p></main>
    </body></html>"""
    f_dormant = check_interstitial_friction(dormant_modal_html)
    check(
        "adversarial_dormant_hidden_modals_ignored",
        len(f_dormant) == 0,
        f"display:none dormant modals must NOT trigger F-ENG-005; got {[f['id'] for f in f_dormant]}"
    )

    
    # 18. Adversarial Probe: Nested unstyled modal inside display:none wrapper (Claude's 5th gap)
    hidden_wrapper_modal_html = """<!DOCTYPE html><html><body>
    <div style="display:none;">
      <div class="modal newsletter-popup">
        <h2>Dormant React/Bootstrap Modal</h2>
        <input type="email"><button>Submit</button>
      </div>
    </div>
    <div class="overlay">Unrelated single overlay class</div>
    <header class="hero">
      <h1>Payment Engine for Modern Marketplaces</h1>
      <a href="/start" class="btn btn-primary">Start Free</a>
    </header>
    <main><h2 id="overview">Overview</h2><p>Content.</p></main>
    </body></html>"""
    f_hidden_wrapper = check_interstitial_friction(hidden_wrapper_modal_html)
    check(
        "adversarial_hidden_wrapper_protects_child_modal",
        len(f_hidden_wrapper) == 0,
        f"modal inside display:none wrapper must NOT trigger F-ENG-005; got {[f['id'] for f in f_hidden_wrapper]}"
    )

    
    # 19. Adversarial Probe: Unclosed <p> tag inside hidden wrapper must NOT blind detector to later visible modal
    malformed_unclosed_p_html = """<!DOCTYPE html><html><body>
    <div style="display:none;">
      <p>Unclosed paragraph text inside hidden wrapper
      <div class="modal newsletter-popup">...</div>
    </div>

    <!-- Genuinely visible blocking modal later in document: -->
    <div class="cookie-wall email-capture-gate">
      <h2>Blocking overlay</h2>
    </div>
    <div class="paywall-gate">Blocked content</div>
    <main><h1>Real Site</h1><p>Content.</p></main>
    </body></html>"""
    f_unclosed_p = check_interstitial_friction(malformed_unclosed_p_html)
    check(
        "adversarial_unclosed_p_does_not_blind_later_modal",
        any(f["id"] == "F-ENG-005" for f in f_unclosed_p),
        f"later visible modal must be caught; got {[f['id'] for f in f_unclosed_p]}"
    )

    
    # 20. Adversarial Probe: Unclosed <nav> (WordPress pattern) must NOT fabricate F-ENG-003/004 and must NOT miss F-ENG-001
    wordpress_malformed_nav_html = """<!DOCTYPE html><html><body>
    <nav class="top-nav">
      <ul><li><a href="/docs">Docs</a></li></ul>
    <!-- Unclosed <nav> tag -->
    <header class="hero">
      <h1>Real-Time Fraud Detection Engine for Payment Processors</h1>
      <p class="hero-subhead">Stop 99.8% of fraudulent transactions with sub-10ms AI decisioning.</p>
      <a href="/signup" class="btn btn-primary">Start Free Trial</a>
    </header>
    <main>
      <h2>Flexible Billing Architecture</h2><p>Billing info.</p>
      <h2>Real-Time Compliance Engine</h2><p>Compliance info.</p>
      <h2>Automated Chargeback Protection</h2><p>Chargeback info.</p>
    </main></body></html>"""
    f_wp = audit_engagement_ux(wordpress_malformed_nav_html, "https://wp-test.com")
    wp_rule_ids = [f["id"] for f in f_wp]
    check(
        "adversarial_unclosed_nav_no_false_positives_and_catches_real_issues",
        ("F-ENG-003" not in wp_rule_ids) and ("F-ENG-004" not in wp_rule_ids) and ("F-ENG-001" in wp_rule_ids),
        f"must not fabricate F-ENG-003/004 and must catch F-ENG-001; got {wp_rule_ids}"
    )

    
    # 21. Adversarial Probe: Mega-menu dropdown panel legitimately containing <header>/<article> inside <nav>
    megamenu_html = """<!DOCTYPE html><html><body>
    <nav class="top-nav">
      <div class="nav-links"><a href="/features">Features</a></div>
      <div class="dropdown-panel">
        <header><h3>This Week's Featured Post</h3></header>
        <article class="promo-card">
          <h4>Developer Quickstart Guide</h4>
          <p>Get up and running with our SDK in under five minutes with copy-paste code snippets.</p>
          <a href="/signup" class="btn btn-primary">Sign Up Free</a>
        </article>
      </div>
    </nav>
    <header class="hero">
      <h1>Unleash Tomorrow</h1>
      <p class="hero-subhead">The next-generation framework for modern enterprise application development.</p>
    </header>
    <main>
      <h2 id="core-architecture">Core Architecture</h2>
      <p>Detailed architecture description.</p>
      <h2 id="benchmarks">Performance Benchmarks</h2>
      <p>Detailed benchmark description.</p>
    </main></body></html>"""
    f_mm = audit_engagement_ux(megamenu_html, "https://megamenu-test.com")
    mm_rule_ids = [f["id"] for f in f_mm]
    check(
        "adversarial_megamenu_dropdown_chrome_isolation",
        ("F-ENG-003" in mm_rule_ids) and ("F-ENG-004" in mm_rule_ids) and ("F-ENG-001" not in mm_rule_ids) and ("F-ENG-006" not in mm_rule_ids),
        f"mega-menu dropdown must isolate chrome: F-ENG-003/004 must fire, F-ENG-001/006 must NOT; got {mm_rule_ids}"
    )

    # 22. Adversarial Probe: HTML5 native <dialog> element is hidden by default unless carrying 'open' attribute
    dialog_html = """<!DOCTYPE html><html><body>
    <!-- Dormant native HTML5 dialogs without 'open' attribute: hidden by browser default -->
    <dialog class="modal" id="newsletter-modal"><h2>Subscribe</h2></dialog>
    <dialog class="lightbox" id="image-viewer"><h2>Image</h2></dialog>
    <header class="hero">
      <h1>Cloud Infrastructure Engine</h1>
      <a href="/start" class="btn">Start</a>
    </header>
    <main><h2 id="a">Section A</h2><p>P1</p></main>
    </body></html>"""
    f_dialog = check_interstitial_friction(dialog_html)
    check(
        "adversarial_native_dialog_hidden_by_default",
        len(f_dialog) == 0,
        f"native dialogs without 'open' attribute must NOT trigger F-ENG-005; got {[f['id'] for f in f_dialog]}"
    )

    passed = sum(1 for r in results if r["pass"])
    print(f"\nSkill 5 Comprehensive Battery: {passed}/{len(results)} passed")
    return results


if __name__ == "__main__":
    run_unit_tests()
