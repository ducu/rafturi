"""Review text -> HTML: splits a Goodreads review into my own comments and the passages
I quoted from the book, and folds long reviews behind "arată tot".

The quote detection was refined over many rounds against real reviews; see the
docstrings before changing any rule.
"""
import json, re, html
from email.utils import parsedate_to_datetime

RO_MONTHS = ['ianuarie','februarie','martie','aprilie','mai','iunie','iulie',
             'august','septembrie','octombrie','noiembrie','decembrie']

SENT_SPLIT = re.compile(r'(?<=[.!?…])\s+(?=[A-ZĂÂÎȘȚ0-9„"“«\-])')
CAP = 100

def fmt_date(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except Exception:
        return None
    return "%d %s %d" % (dt.day, RO_MONTHS[dt.month-1], dt.year)

# A handful of older RSS entries carry raw cp1252 bytes (0x80-0x9F) where the feed
# should have been decoded as Windows-1252 -- e.g. „ ” – show up as stray control
# chars instead. Map them back to the punctuation they were meant to be.
CP1252_FIX = {
    0x80: '€', 0x82: '‚', 0x83: 'ƒ', 0x84: '„', 0x85: '…',
    0x86: '†', 0x87: '‡', 0x88: 'ˆ', 0x89: '‰', 0x8A: 'Š',
    0x8B: '‹', 0x8C: 'Œ', 0x8E: 'Ž', 0x91: '‘', 0x92: '’',
    0x93: '“', 0x94: '”', 0x95: '•', 0x96: '–', 0x97: '—',
    0x98: '˜', 0x99: '™', 0x9A: 'š', 0x9B: '›', 0x9C: 'œ',
    0x9E: 'ž', 0x9F: 'Ÿ',
}

def review_to_paragraphs(review_html):
    if not review_html or not review_html.strip():
        return []
    review_html = review_html.translate(CP1252_FIX)
    # treat any <br/> as a paragraph separator
    parts = re.split(r'\s*<br\s*/?>\s*', review_html.strip())
    out = []
    for p in parts:
        text = re.sub(r'<[^>]+>', '', p)
        text = html.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text).strip()
        if text:
            out.append(text)
    return out

def find_quote_ranges(text, para_starts):
    """Find (outer_start, outer_end, inner_start, inner_end) spans delimited by
    matching quote-mark pairs, possibly spanning multiple joined paragraphs.

    « ... » are always paired by simple regex (used cleanly/non-nested in this data).

    For „ “ ” the source is not typographically consistent, and both of these occur,
    sometimes in the very same review:
      - genuine local nesting: “ used as a fresh opener each time a quote-within-a-quote
        starts (e.g. a foreign phrase or a line of dialogue quoted inside a longer
        passage), properly closed with ”.
      - typos: a „ (or “) mistakenly closed with a second “ instead of the proper ”, or
        a straight " mismatched with a curly ” -- no nesting intended, just a wrong key.
    Resolving this is two passes rather than a single global choice, since one typo
    elsewhere in a review must not stop correctly-nested quotes from resolving:
      pass 1 -- strict stack matching (push on „/“, pop on ”); a close only ends a range
        when it empties the stack (an inner open/close pair is absorbed into the eventual
        outer range's text, never its own range); a ” with nothing on the stack, or a „/“
        that never finds its ”, is simply left unresolved for pass 2.
      pass 2 -- whatever „“”" marks pass 1 left unresolved (including plain "..." pairs)
        are paired sequentially in the order they appear, tolerating mismatched mark types.

    A real quote, in these reviews, always opens a new paragraph (it may then run
    across several paragraphs, optionally trailed by a page number); a quote mark
    appearing mid-paragraph, after other text of the author's own, is inline --
    a scare-quoted word/phrase or a quoted title/line folded into the author's own
    sentence -- and is excluded here (marks kept, inherits the surrounding style),
    regardless of how many words it spans."""
    ranges = []
    for m in re.finditer(r'«([^«»]*)»', text, re.S):
        ranges.append((m.start(), m.end(), m.start(1), m.end(1)))
    covered = bytearray(len(text))
    for s, e, _, _ in ranges:
        for i in range(s, e):
            covered[i] = 1

    # Pass 1: stack matching for „ / “ ... ”. „ always opens. ” always closes (when
    # there's an open to close). “ is ambiguous in this data -- sometimes a fresh
    # nested opener (a short quoted phrase inside a longer quote -- possibly lowercase,
    # e.g. “the response to Auschwitz”), sometimes a typo for the proper ” closer.
    # Telling them apart locally: a genuine opener is followed immediately (no space)
    # by a letter, starting its own quoted word/phrase/sentence right there; a
    # mismatched closer is followed by a space, a citation, or punctuation -- there's
    # no new quoted text glued right onto it.
    stack = []
    for m in re.finditer(r'[„“”]', text):
        pos = m.start()
        if covered[pos]:
            continue
        ch = m.group()
        if ch == '„':
            stack.append(pos)
        elif ch == '“' and (not stack or text[pos + 1:pos + 2].isalpha()):
            stack.append(pos)
        elif stack:
            s = stack.pop()
            for i in range(s, m.end()):
                covered[i] = 1
            if not stack:
                ranges.append((s, m.end(), s + 1, m.start()))

    # Pass 2: whatever quote-like marks remain uncovered (unresolved „/“ opens or lone
    # ” closes left over from pass 1, plus plain "..." pairs) are paired sequentially.
    leftover_positions = [m.start() for m in re.finditer(r'[„“”"]', text) if not covered[m.start()]]
    for i in range(0, len(leftover_positions) - 1, 2):
        s, e = leftover_positions[i], leftover_positions[i + 1]
        ranges.append((s, e + 1, s + 1, e))

    def closes_cleanly(outer_e):
        # What immediately follows the closing mark, within the SAME paragraph, decides
        # whether this was a real, self-contained quote or just a title/phrase folded
        # into a longer sentence of the author's own (e.g. "Citind X" ar putea fi...").
        # A page citation "(p.12)", the paragraph simply ending there (a following
        # paragraph -- a link, a new remark, whatever -- doesn't count), or a new
        # (capitalized) sentence are all fine endings; text that carries straight on in
        # lowercase means the quote mark was only wrapping a phrase mid-sentence.
        rest = text[outer_e:].split('\n', 1)[0].lstrip()
        if not rest or rest[0] in '([':
            return True
        first_alpha = next((c for c in rest if c.isalpha()), None)
        if first_alpha is None:
            return True
        return not first_alpha.islower()

    def opens_cleanly(inner_s):
        # A genuine quote starts its own sentence -- capitalized, or a dialogue dash /
        # ellipsis before the first word. Starting directly on a lowercase word (e.g.
        # "că așa ne place...") means it's an elliptical fragment continuing something
        # left unshown, i.e. the author's own aside, not a real quoted sentence.
        s = text[inner_s:].lstrip()
        c = s[:1]
        return not (c.isalpha() and c.islower())

    def starts_cleanly(outer_s):
        # A quote either opens a new paragraph, or -- two quoted sentences can sit
        # back to back in the same paragraph, e.g. "Prima." "A doua propoziție..." --
        # immediately follows the end of the sentence before it (a period, "!", "?",
        # "…"). A colon, a dash, a comma, or a bare word right before the mark (e.g.
        # "scrisese: "Oblomov e o..."", "vorba lui X: "...") means the quote is folded
        # in as the object of the author's own sentence, not a freestanding one.
        if outer_s in para_starts:
            return True
        before = text[:outer_s].rstrip()
        return bool(before) and before[-1] in '.!?…'

    ranges = [r for r in ranges if starts_cleanly(r[0]) and opens_cleanly(r[2]) and closes_cleanly(r[1])]
    ranges.sort(key=lambda r: r[0])
    filtered = []
    last_end = -1
    for r in ranges:
        if r[0] >= last_end:
            filtered.append(r)
            last_end = r[1]
    return filtered

# One review ("Pentru Europa...", Adrian Marino) mixes straight and curly quote marks
# so heavily -- including a doubled „"..."„ mark around a nested quote, and at least one
# „ with no matching ” anywhere in the text -- that no general pairing rule resolves it
# correctly. The user confirmed by hand that its entire body (bar the trailing page
# citation) is one continuous quote, so that specific review is special-cased here
# rather than distorting the general algorithm to fit one broken source record.
PENTRU_EUROPA_FINGERPRINT = 'Modul cum spiritul și cultura românească'

def build_fragments(paragraphs):
    """Split paragraphs into (pi, type, text) fragments, where type is 'quote'
    for text inside matched quote marks (marks stripped) and 'comment' otherwise.
    A quote span may run across several original paragraphs."""
    if paragraphs and PENTRU_EUROPA_FINGERPRINT in paragraphs[0]:
        fragments = []
        for pi, p in enumerate(paragraphs):
            if re.match(r'^\(\d{4}\)', p.strip()):
                fragments.append((pi, 'comment', p.strip()))
            else:
                fragments.append((pi, 'quote', p.strip('"').strip()))
        return fragments

    SEP = '\n'
    full_text = SEP.join(paragraphs)
    poffsets = []
    pos = 0
    for p in paragraphs:
        poffsets.append((pos, pos + len(p)))
        pos += len(p) + len(SEP)
    para_starts = set(ps for ps, pe in poffsets)

    segs = []
    pos = 0
    for outer_s, outer_e, inner_s, inner_e in find_quote_ranges(full_text, para_starts):
        if outer_s > pos:
            segs.append(('comment', pos, outer_s))
        if inner_s < inner_e:
            segs.append(('quote', inner_s, inner_e))
        pos = outer_e
    if pos < len(full_text):
        segs.append(('comment', pos, len(full_text)))

    fragments = []
    for typ, s, e in segs:
        for pi, (ps, pe) in enumerate(poffsets):
            os_, oe_ = max(s, ps), min(e, pe)
            if os_ < oe_:
                t = full_text[os_:oe_].strip()
                if t:
                    fragments.append((pi, typ, t))
    return fragments

def build_review_block(paragraphs):
    if not paragraphs:
        return ''

    fragments = build_fragments(paragraphs)
    frag_types = [f[1] for f in fragments]

    def esc(t):
        return html.escape(t, quote=False)

    marked_fis = set()
    def cls_for(fi):
        c = 'entry-quoted' if frag_types[fi] == 'quote' else 'entry-comment'
        # Mark the opening „ on every quote run's first fragment, not just the
        # review's very first quote -- a review can have several separate quotes,
        # each starting its own run after a comment/citation in between. A single
        # fragment can be rendered twice (once truncated in the teaser, again in
        # full in the "rest" after "arată tot"), so track which fi's have already
        # gotten the mark to avoid stamping it on both renderings.
        if (frag_types[fi] == 'quote' and (fi == 0 or frag_types[fi - 1] != 'quote')
                and fi not in marked_fis):
            c += ' first-quote'
            marked_fis.add(fi)
        return c

    def merge_citations(items):
        # A short parenthetical comment fragment right after a quote -- "(p.103)",
        # "(17 iunie 1935, p.30)" -- is a page citation, not a new remark: fold it into
        # the end of the quote paragraph it belongs to instead of giving it its own line.
        # A comment fragment that's pure punctuation (just the "." left over between two
        # back-to-back quoted sentences) isn't a remark either -- glue it onto whatever
        # precedes it, plainly, instead of giving a lone period its own line. If there's
        # nothing before it to glue onto (it landed right at a teaser/rest split), it's
        # dropped -- a standalone "." carries nothing worth showing on its own.
        out = []
        for fi, t in items:
            letterless = frag_types[fi] == 'comment' and not any(c.isalpha() for c in t)
            is_citation = (
                frag_types[fi] == 'comment' and t.strip().startswith('(') and
                len(t.split()) <= 12 and out and frag_types[out[-1][0]] == 'quote'
            )
            if is_citation:
                prev_fi, prev_t = out[-1]
                out[-1] = (prev_fi, prev_t + '\x00' + t)
            elif letterless and out:
                prev_fi, prev_t = out[-1]
                out[-1] = (prev_fi, prev_t + '\x01' + t)
            elif letterless:
                continue
            else:
                out.append((fi, t))
        return out

    def render_item(fi, t, tag):
        if '\x00' not in t and '\x01' not in t:
            return '<%s class="%s">%s</%s>' % (tag, cls_for(fi), esc(t), tag)
        parts = re.split(r'([\x00\x01])', t)
        out_html = [esc(parts[0])]
        i = 1
        while i < len(parts):
            marker, chunk = parts[i], parts[i + 1] if i + 1 < len(parts) else ''
            if marker == '\x00':
                out_html.append('<span class="entry-comment"> %s</span>' % esc(chunk))
            else:
                out_html.append(esc(chunk))
            i += 2
        return '<%s class="%s">%s</%s>' % (tag, cls_for(fi), ''.join(out_html), tag)

    all_sentences = []
    for fi, (pi, typ, text) in enumerate(fragments):
        sents = [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]
        if not sents:
            continue
        for s in sents:
            all_sentences.append((fi, s))
    total_words = sum(len(s.split()) for _, s in all_sentences)

    if total_words <= CAP:
        items = merge_citations([(fi, t) for fi, (pi, typ, t) in enumerate(fragments)])
        ps = ''.join(render_item(fi, t, 'p') for fi, t in items)
        return '<blockquote class="entry-quote">%s</blockquote>' % ps

    acc_words = 0
    cut_idx = len(all_sentences)
    for idx, (fi, s) in enumerate(all_sentences):
        w = len(s.split())
        if acc_words > 0 and acc_words + w > CAP:
            cut_idx = idx
            break
        acc_words += w
    if cut_idx == 0:
        cut_idx = 1

    teaser_sents = all_sentences[:cut_idx]
    rest_sents = all_sentences[cut_idx:]

    def regroup(sents):
        paras = []
        cur_fi = None
        cur = []
        for fi, s in sents:
            if cur and fi != cur_fi:
                paras.append((cur_fi, ' '.join(cur)))
                cur = []
            cur.append(s)
            cur_fi = fi
        if cur:
            paras.append((cur_fi, ' '.join(cur)))
        return paras

    teaser_paras = merge_citations(regroup(teaser_sents))
    rest_paras = merge_citations(regroup(rest_sents))

    teaser_html = '<br><br>'.join(render_item(fi, t, 'span') for fi, t in teaser_paras)
    toggle = ('<span class="toggle"><span class="lbl-more"> arată tot</span>'
              '<span class="lbl-less"> arată mai puțin</span>'
              '<span class="chevron" aria-hidden="true">&#8250;</span></span>')
    rest_html = ''.join(render_item(fi, t, 'p') for fi, t in rest_paras)

    return ('<blockquote class="entry-quote"><details><summary>%s%s</summary>'
            '<div class="quote-rest">%s</div></details></blockquote>') % (teaser_html, toggle, rest_html)
