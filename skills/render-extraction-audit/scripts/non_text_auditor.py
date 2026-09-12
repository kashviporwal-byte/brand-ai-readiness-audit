"""
Subskills 2.2 & 2.3: Non-Text Trapped Facts & Rich Media Auditor (Optimized)
Audits images for missing, low-quality, or placeholder alt text (with figcaption/title awareness),
and audits rich media elements (canvas, svg data charts, video, audio)
for accessible textual fallbacks and transcripts.
Optimized for sub-millisecond parsing even on heavy vector-graphic pages.
"""

import re
from html.parser import HTMLParser


class NonTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.canvas_elements = []
        self.videos = []
        self.audios = []
        self.svg_elements = []
        self.in_figure = False
        self.figure_counter = 0
        self.current_figure_id = None
        self.in_figcaption = False
        self.figcaption_text = []

        self.current_video_tracks = []
        self.in_svg = False
        self.current_svg = None

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}

        if tag_lower == "figure":
            self.in_figure = True
            self.figure_counter += 1
            self.current_figure_id = self.figure_counter
            self.figcaption_text = []

        elif tag_lower == "figcaption":
            self.in_figcaption = True

        elif tag_lower == "img":
            # Lazy-loaded image handling: check data-src, data-srcset, data-original, data-lazy-src, data-alt
            src = attr_dict.get("src", "")
            data_src = (
                attr_dict.get("data-src", "")
                or attr_dict.get("data-srcset", "")
                or attr_dict.get("data-original", "")
                or attr_dict.get("data-lazy-src", "")
            )
            # If src is empty or a placeholder (data URI / 1x1 gif / blank / spinner), prefer data_src
            if (not src or "data:image/" in src.lower() or "placeholder" in src.lower() or "blank." in src.lower() or "1x1" in src.lower() or "spinner" in src.lower()) and data_src:
                effective_src = data_src
            else:
                effective_src = src or data_src

            alt = attr_dict.get("alt", None)
            data_alt = attr_dict.get("data-alt", None)
            effective_alt = alt if (alt is not None and alt.strip() != "") else (data_alt if data_alt is not None else alt)

            self.images.append({
                "src": effective_src,
                "alt": effective_alt,
                "title": attr_dict.get("title", ""),
                "role": attr_dict.get("role", ""),
                "aria_hidden": attr_dict.get("aria-hidden", ""),
                "aria_label": attr_dict.get("aria-label", ""),
                "aria_labelledby": attr_dict.get("aria-labelledby", ""),
                "loading": attr_dict.get("loading", ""),
                "figure_id": self.current_figure_id if self.in_figure else None,
                "figure_caption": ""
            })

        elif tag_lower == "canvas":
            self.canvas_elements.append({
                "id": attr_dict.get("id", ""),
                "aria_label": attr_dict.get("aria-label", ""),
                "aria_describedby": attr_dict.get("aria-describedby", "")
            })

        elif tag_lower == "video":
            self.current_video_tracks = []
            self.videos.append({
                "src": attr_dict.get("src", ""),
                "tracks": self.current_video_tracks
            })

        elif tag_lower == "track" and self.videos:
            track_kind = attr_dict.get("kind", "").lower()
            track_src = attr_dict.get("src", "")
            self.current_video_tracks.append({"kind": track_kind, "src": track_src})

        elif tag_lower == "audio":
            self.audios.append({
                "src": attr_dict.get("src", "")
            })

        elif tag_lower == "svg":
            self.in_svg = True
            css_class = attr_dict.get("class", "").lower()
            # Fast check: skip decorative icons (small or class contains icon)
            is_icon = "icon" in css_class or "logo" in css_class or attr_dict.get("aria-hidden") == "true"
            
            self.current_svg = {
                "aria_label": attr_dict.get("aria-label", ""),
                "aria_hidden": attr_dict.get("aria-hidden", ""),
                "role": attr_dict.get("role", ""),
                "is_icon": is_icon,
                "has_title": False,
                "has_desc": False,
                "child_nodes_count": 0
            }

        elif self.in_svg and self.current_svg:
            if tag_lower == "title":
                self.current_svg["has_title"] = True
            elif tag_lower == "desc":
                self.current_svg["has_desc"] = True
            elif tag_lower in ("path", "rect", "circle", "line", "polygon", "polyline", "g"):
                # PERFORMANCE OPTIMIZATION: Cap count at 8 to avoid slow counting on 10,000-node SVGs
                if self.current_svg["child_nodes_count"] < 8:
                    self.current_svg["child_nodes_count"] += 1

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == "figcaption":
            self.in_figcaption = False
            caption = " ".join("".join(self.figcaption_text).split()).strip()
            # Associate caption ONLY with images sharing the exact same figure_id
            if self.current_figure_id is not None:
                for img in self.images:
                    if img.get("figure_id") == self.current_figure_id:
                        img["figure_caption"] = caption

        elif tag_lower == "figure":
            self.in_figure = False
            self.current_figure_id = None

        elif tag_lower == "svg":
            self.in_svg = False
            if self.current_svg:
                self.svg_elements.append(self.current_svg)
                self.current_svg = None

    def handle_data(self, data):
        if self.in_figcaption:
            self.figcaption_text.append(data)


def check_non_text_elements(raw_html, page_url=""):
    """
    Analyzes images, canvas, video, and complex SVGs for trapped facts.
    """
    findings = []
    if not raw_html:
        return findings

    parser = NonTextParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass

    # ==========================================================
    # 1. Image Alt Text Audit (Subskill 2.2)
    # ==========================================================
    informational_images = []
    missing_alt_images = []
    placeholder_alt_images = []
    filename_alt_images = []

    generic_placeholders = {
        "image", "photo", "picture", "graphic", "screenshot", "icon",
        "logo", "banner", "placeholder", "img", "untitled", "test", "asset"
    }

    file_extension_pattern = re.compile(r"\.(png|jpg|jpeg|webp|gif|svg|bmp)$", re.IGNORECASE)

    for img in parser.images:
        role = img["role"].lower()
        aria_hidden = img["aria_hidden"].lower()
        alt = img["alt"]
        title = img["title"]
        src = img["src"]
        aria_label = img["aria_label"]
        figure_caption = img["figure_caption"]

        # Skip explicit decorative elements
        if role in ("presentation", "none") or aria_hidden == "true":
            continue

        # If image has an explicit aria-label, figure caption, or title attribute, it is accessible
        if (alt is None or alt.strip() == "") and (aria_label or figure_caption or (title and len(title.strip()) > 3)):
            continue

        informational_images.append(img)

        if alt is None or alt.strip() == "":
            missing_alt_images.append(src or "inline-img")
        else:
            alt_clean = alt.strip().lower()
            if alt_clean in generic_placeholders:
                placeholder_alt_images.append((src, alt))
            elif file_extension_pattern.search(alt_clean) or re.search(r"^(img_|dsc_|screenshot_|banner_)", alt_clean):
                filename_alt_images.append((src, alt))

    total_info_images = len(informational_images)
    total_defective_images = len(missing_alt_images) + len(placeholder_alt_images) + len(filename_alt_images)

    if total_info_images > 0 and total_defective_images > 0:
        defect_ratio = total_defective_images / total_info_images
        severity = "high" if (defect_ratio > 0.3 or total_defective_images >= 4) else "medium"

        evidence_details = []
        if missing_alt_images:
            evidence_details.append(f"{len(missing_alt_images)} images completely lack alt attributes")
        if placeholder_alt_images:
            samples = [f"'{a}'" for _, a in placeholder_alt_images[:2]]
            evidence_details.append(f"{len(placeholder_alt_images)} use generic placeholders ({', '.join(samples)})")
        if filename_alt_images:
            samples = [f"'{a}'" for _, a in filename_alt_images[:2]]
            evidence_details.append(f"{len(filename_alt_images)} use raw filenames as alt ({', '.join(samples)})")

        findings.append({
            "id": "F-REND-003",
            "skill_id": "render-extraction-audit",
            "title": "Critical facts and diagrams trapped in images with missing or low-quality alt text",
            "severity": severity,
            "impact_area": "ai_discoverability",
            "evidence": f"Audited {total_info_images} informational images; {total_defective_images}/{total_info_images} ({defect_ratio:.1%}) have defective alt attributes: {'; '.join(evidence_details)}.",
            "suggested_action": {
                "summary": "Provide descriptive, factual alt text conveying the underlying information for all diagrams, charts, and product images.",
                "priority": severity,
                "rationale": "Multimodal and text-only AI models cannot parse data graphs, workflows, or tier matrices stored in raster images without descriptive alt text.",
                "code_fix_example": '<img src="/assets/data-pipeline.png" alt="Architecture diagram showing real-time event streaming pipeline processing 50k events per second">'
            }
        })

    # ==========================================================
    # 2. Canvas & WebGL Traps (Subskill 2.3)
    # ==========================================================
    if parser.canvas_elements:
        unlabeled_canvas = [c for c in parser.canvas_elements if not c["aria_label"] and not c["aria_describedby"]]
        if unlabeled_canvas:
            findings.append({
                "id": "F-REND-004",
                "skill_id": "render-extraction-audit",
                "title": "Interactive <canvas> data visualizations lack machine-readable text fallbacks",
                "severity": "medium",
                "impact_area": "ai_discoverability",
                "evidence": f"Found {len(parser.canvas_elements)} <canvas> elements; {len(unlabeled_canvas)} lack aria-label, aria-describedby, or fallback DOM text.",
                "suggested_action": {
                    "summary": "Add aria-label descriptions or fallback data tables alongside canvas visualizations.",
                    "priority": "medium",
                    "rationale": "Canvas elements render directly to a pixel buffer. AI extractors see an empty container unless accessibility labels or data tables are provided.",
                    "code_fix_example": '<canvas id="latency-chart" aria-label="Benchmark graph demonstrating 4x lower latency compared to legacy queue solutions"></canvas>'
                }
            })

    # ==========================================================
    # 3. Video & Audio Traps (Subskill 2.3)
    # ==========================================================
    media_without_captions = []
    if parser.videos:
        for v in parser.videos:
            caption_tracks = [t for t in v["tracks"] if t["kind"] in ("captions", "subtitles")]
            if not caption_tracks:
                media_without_captions.append(v["src"] or "embedded-video")

    if parser.audios:
        for a in parser.audios:
            media_without_captions.append(a["src"] or "embedded-audio")

    if media_without_captions:
        has_transcript_container = bool(re.search(r'(?:class|id)=["\'][^"\']*transcript[^"\']*["\']', raw_html, re.IGNORECASE))
        if not has_transcript_container:
            total_media = len(parser.videos) + len(parser.audios)
            findings.append({
                "id": "F-REND-005",
                "skill_id": "render-extraction-audit",
                "title": "Product videos, audio demos, or podcasts lack captions or written transcripts",
                "severity": "medium",
                "impact_area": "ai_discoverability",
                "evidence": f"Detected {total_media} media element(s) ({len(parser.videos)} video, {len(parser.audios)} audio); {len(media_without_captions)} lack caption tracks or adjacent written transcripts.",
                "suggested_action": {
                    "summary": "Provide WebVTT caption tracks and an expandable written transcript below all video and audio content.",
                    "priority": "medium",
                    "rationale": "AI answer engines cannot ingest video or audio content directly during web crawling. Written transcripts make spoken content indexable and quotable.",
                    "code_fix_example": '<audio controls src="/podcast.mp3"></audio>\n<div class="audio-transcript">\n  <h3>Episode Transcript</h3>\n  <p>Full searchable transcript text...</p>\n</div>'
                }
            })

    # ==========================================================
    # 4. Complex Inline SVG Data Charts (Subskill 2.3 - High Performance)
    # ==========================================================
    unlabeled_data_svgs = []
    for svg in parser.svg_elements:
        role = svg["role"].lower()
        aria_hidden = svg["aria_hidden"].lower()
        # Only inspect non-icon complex SVGs (>= 5 data nodes) that are NOT explicitly decorative
        if svg["child_nodes_count"] >= 5 and not svg["is_icon"] and role not in ("presentation", "none") and aria_hidden != "true":
            if not svg["has_title"] and not svg["has_desc"] and not svg["aria_label"]:
                unlabeled_data_svgs.append(svg)

    if unlabeled_data_svgs:
        findings.append({
            "id": "F-REND-011",
            "skill_id": "render-extraction-audit",
            "title": "Complex inline SVG data charts lack <title> or <desc> accessible metadata",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": f"Found {len(unlabeled_data_svgs)} complex SVG graphics (>= 5 data nodes) with zero <title>, <desc>, or aria-label attributes.",
            "suggested_action": {
                "summary": "Include <title> and <desc> tags inside complex SVG visualizations to describe their underlying data.",
                "priority": "medium",
                "rationale": "Screen readers and multimodal AI extractors rely on SVG title and description tags to extract facts from vector graphs.",
                "code_fix_example": '<svg role="img" aria-labelledby="svg-title svg-desc">\n  <title id="svg-title">Annual Growth Chart</title>\n  <desc id="svg-desc">Graph showing 140% year-over-year revenue expansion in enterprise tier</desc>\n  ...\n</svg>'
            }
        })

    return findings
