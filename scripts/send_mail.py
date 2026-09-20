#!/usr/bin/env python3
"""
발행 메일 발송 — 정제판(또는 규칙표 판)이 올라가면 지정 수신자에게 요약 메일을 보냅니다.

  python3 scripts/send_mail.py [날짜] [--dry-run]

설정: watchlist.yml 의 mail: 블록(수신자·제목·방식). 비밀 정보는 환경 변수(GitHub Secrets)로만 받습니다.
  방식 gas  : GAS_URL, GAS_TOKEN        — 기존 사내 Apps Script(공수 시스템)의 다우오피스 발송 함수를 그대로 재사용
  방식 smtp : DAOU_SMTP_USER, DAOU_SMTP_PASS (+ 선택 DAOU_SMTP_HOST, DAOU_SMTP_PORT)  — 다우오피스 메일 계정으로 직접 발송
  방식 api  : DAOU_API_URL, DAOU_API_KEY                                               — 다우오피스 API 를 직접 호출
--dry-run 이면 보내지 않고 out/mail-<날짜>.html 에 본문만 저장합니다.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib as B  # noqa: E402

DATA = B.ROOT / "data"
KST = timezone(timedelta(hours=9))
SITE_URL = "https://sugilyang.github.io/ets-news/"
GRADE_LABEL = {"A": "A 즉시", "B": "B", "C": "C"}
GRADE_COLOR = {"A": "#b3261e", "B": "#111417", "C": "#6b7280"}


def esc(s) -> str:
    import html
    return html.escape(str(s or ""), quote=True)


def items_of(d: dict) -> list[dict]:
    return [it for s in d.get("sections", []) for g in s.get("groups", []) for it in g.get("items", [])]


def guide_rows(d: dict) -> list[tuple[dict, str]]:
    by = {it["id"]: it for it in items_of(d)}
    return [(by[g["item_id"]], g.get("say", "")) for g in d.get("guide", []) if g.get("item_id") in by]


def build_html(d: dict, wl: dict) -> tuple[str, str]:
    """→ (제목, HTML 본문). 메일 클라이언트 호환을 위해 인라인 스타일·표 기반."""
    site = (wl.get("site") or {}).get("name", "이티에스 시장 동향")
    day = d.get("date", ""); no = d.get("issue_no", 0)
    cat_title = {c["id"]: c.get("title", c["id"]) for c in wl.get("categories") or []}
    items = items_of(d)
    a_items = [it for it in items if it.get("grade") == "A"]
    grows = guide_rows(d)
    refined = "Claude 정제판" if d.get("refined") else "규칙표 판"
    subject = f"[{site}] 제{no}호 {day} — {B.strip_tags(d.get('summary',''))[:60]}"
    paper = f"{SITE_URL}briefings/{day}.html"; report = f"{SITE_URL}reports/{day}.html"

    def badge(g):
        return (f'<span style="display:inline-block;font:700 11px/16px sans-serif;padding:0 6px;border-radius:2px;'
                f'background:{GRADE_COLOR.get(g,"#6b7280")};color:#fff;white-space:nowrap">{esc(GRADE_LABEL.get(g,g))}</span>')

    def stars(n):
        n = max(1, min(5, int(n or 2)))
        return f'<span style="color:#c9a227">{"★"*n}</span><span style="color:#d9d5cc">{"★"*(5-n)}</span>'

    rows = ""
    for k, (it, say) in enumerate(grows, 1):
        parts = say.split(" → ", 1)
        sig, act = (parts[0], parts[1]) if len(parts) == 2 else (say, "")
        rows += (f'<tr><td style="padding:6px 8px;border-bottom:1px solid #e5e5e5;text-align:center">{k}</td>'
                 f'<td style="padding:6px 8px;border-bottom:1px solid #e5e5e5;text-align:center;white-space:nowrap">{badge(it.get("grade","C"))}</td>'
                 f'<td style="padding:6px 8px;border-bottom:1px solid #e5e5e5;font-weight:700">{esc(it.get("entity") or "-")}</td>'
                 f'<td style="padding:6px 8px;border-bottom:1px solid #e5e5e5">{esc(sig)}</td>'
                 f'<td style="padding:6px 8px;border-bottom:1px solid #e5e5e5;font-weight:700;color:#0b3d35">{esc(act)}</td>'
                 f'<td style="padding:6px 8px;border-bottom:1px solid #e5e5e5;font-size:11px;color:#6b7280">{esc(it.get("src",""))} {stars(it.get("rel",2))}'
                 f'{" · <a href=%s>원문</a>" % esc(it["url"]) if it.get("url") else ""}</td></tr>')
    if not rows:
        rows = '<tr><td colspan="6" style="padding:8px;color:#6b7280">오늘은 영업 신호가 없습니다.</td></tr>'

    secs = ""
    for s in d.get("sections", []):
        its = [it for g in s.get("groups", []) for it in g.get("items", []) if it.get("grade") in ("A", "B")]
        if not its:
            continue
        li = ""
        for it in its:
            h = f'<a href="{esc(it["url"])}" style="color:#111417;text-decoration:none;font-weight:700">{it.get("h","")}</a>' if it.get("url") else f'<b>{it.get("h","")}</b>'
            b = f'<div style="color:#2a2f36;font-size:13px;margin-top:2px">{it.get("b","")}</div>' if it.get("b") else ""
            meta = f'<div style="font-size:11px;color:#6b7280;margin-top:2px">{esc(it.get("entity") or "")} {esc(it.get("src",""))} {stars(it.get("rel",2))} {" ".join("#"+t for t in (it.get("tags") or [])[:3])}</div>'
            li += f'<div style="padding:8px 0;border-bottom:1px dotted #d9d5cc">{badge(it.get("grade","C"))} {h}{b}{meta}</div>'
        secs += (f'<h3 style="font:700 14px sans-serif;color:#fff;background:#111417;padding:6px 10px;margin:16px 0 4px">'
                 f'{esc(s.get("title",""))} <span style="font-weight:400;color:#c9d3df">{len(its)}건</span></h3>{li}')

    kpi = (f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:10px 0;width:100%"><tr>'
           + "".join(f'<td style="width:25%;padding:8px 10px;border:1px solid #e5e5e5;background:#fbfaf6;vertical-align:top"><div style="font-size:11px;color:#6b7280">{esc(l)}</div>'
                     f'<div style="font:600 {sz} sans-serif;color:{c};line-height:1.25">{esc(v)}</div></td>'
                     for l, v, c, sz in [("즉시보고(A)", len(a_items), "#b3261e", "26px"), ("보고 항목", len(items), "#111417", "26px"),
                                         ("영업 포인트", len(grows), "#111417", "26px"), ("발행", refined, "#0e9b86", "15px")])
           + "</tr></table>")

    html_ = f"""<!DOCTYPE html><html lang="ko"><body style="margin:0;background:#efece4;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#2a2f36">
<div style="max-width:760px;margin:0 auto;background:#fbfaf6;padding:18px 22px;border:1px solid #d9d5cc">
  <div style="border-top:4px solid #1b1f24;border-bottom:3px double #1b1f24;padding:10px 0 8px;text-align:center">
    <div style="font-size:11px;letter-spacing:.3em;color:#6b7280">ETS MARKET INTELLIGENCE</div>
    <div style="font:900 26px serif;color:#111417">{esc(site)}</div>
    <div style="font-size:12.5px;color:#6b7280;margin-top:2px">제{no}호 · {esc(B.kdate(day))} · {refined}</div>
  </div>
  <div style="margin:10px 0 0;font-size:13.5px;line-height:1.6"><b>오늘의 요약</b> {esc(B.strip_tags(d.get("summary","")))}</div>
  {kpi}
  <div style="font:700 13px sans-serif;color:#0b6f60;border-left:4px solid #0e9b86;padding-left:8px;margin:12px 0 6px">오늘의 영업 포인트</div>
  <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:12.5px">
    <thead><tr style="background:#eeece5"><th style="padding:6px 8px;text-align:center">No</th><th style="padding:6px 8px;white-space:nowrap">등급</th><th style="padding:6px 8px;text-align:left">회사</th><th style="padding:6px 8px;text-align:left">사실(신호)</th><th style="padding:6px 8px;text-align:left">영업이 할 일</th><th style="padding:6px 8px;text-align:left">출처</th></tr></thead>
    <tbody>{rows}</tbody></table>
  <div style="margin:14px 0 4px;font-size:13px">
    <a href="{report}" style="display:inline-block;background:#111417;color:#fff;padding:7px 14px;text-decoration:none;font-weight:700;margin-right:6px">보고서 형식 보기</a>
    <a href="{paper}" style="display:inline-block;background:#fff;color:#111417;border:1px solid #111417;padding:6px 14px;text-decoration:none;font-weight:700">신문 형식 보기</a>
  </div>
  {secs}
  <div style="margin-top:18px;border-top:3px double #1b1f24;padding-top:8px;font-size:11px;color:#6b7280;line-height:1.6">
    A·B등급만 메일에 담았습니다. C등급·일반 동향과 지난 호·검색은 사이트에서 보실 수 있습니다.<br>
    {esc(d.get("note",""))}
  </div>
</div></body></html>"""
    return subject, html_


def send_smtp(cfg: dict, to: list[str], cc: list[str], subject: str, html_: str) -> None:
    user = os.environ.get("DAOU_SMTP_USER", ""); pw = os.environ.get("DAOU_SMTP_PASS", "")
    host = os.environ.get("DAOU_SMTP_HOST") or cfg.get("host", "smtp.daouoffice.com")
    port = int(os.environ.get("DAOU_SMTP_PORT") or cfg.get("port", 465))
    if not (user and pw):
        raise SystemExit("DAOU_SMTP_USER / DAOU_SMTP_PASS 환경 변수(GitHub Secrets)가 없습니다.")
    sender = cfg.get("from") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = formataddr((str(Header(cfg.get("from_name", "이티에스 시장 동향"), "utf-8")), sender))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.attach(MIMEText("HTML 메일을 지원하는 클라이언트에서 확인하세요. " + SITE_URL, "plain", "utf-8"))
    msg.attach(MIMEText(html_, "html", "utf-8"))
    ctx = ssl.create_default_context()
    if str(cfg.get("security", "ssl")).lower() == "starttls" or port == 587:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo(); s.starttls(context=ctx); s.login(user, pw); s.sendmail(sender, to + cc, msg.as_string())
    else:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(user, pw); s.sendmail(sender, to + cc, msg.as_string())


def send_api(cfg: dict, to: list[str], cc: list[str], subject: str, html_: str, d: dict) -> None:
    import requests
    url = os.environ.get("DAOU_API_URL") or cfg.get("url", "")
    key = os.environ.get("DAOU_API_KEY", "")
    if not url:
        raise SystemExit("DAOU_API_URL 환경 변수(GitHub Secrets)가 없습니다.")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    hk = cfg.get("key_header", "Authorization")
    if key:
        headers[hk] = (cfg.get("key_prefix", "") + key)
    body_t = cfg.get("body") or {"to": "{to}", "cc": "{cc}", "subject": "{subject}", "content": "{html}", "contentType": "html"}
    def fill(v):
        if isinstance(v, str):
            return (v.replace("{to}", ",".join(to)).replace("{cc}", ",".join(cc)).replace("{subject}", subject)
                     .replace("{html}", html_).replace("{text}", B.strip_tags(d.get("summary", ""))).replace("{url}", SITE_URL))
        if isinstance(v, dict):
            return {k: fill(x) for k, x in v.items()}
        if isinstance(v, list):
            return [fill(x) for x in v]
        return v
    payload = fill(body_t)
    if payload.get("to") == ",".join(to) and cfg.get("to_as_list", True):
        payload["to"] = to; payload["cc"] = cc
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code >= 300:
        raise SystemExit(f"API 응답 {r.status_code}: {r.text[:300]}")
    print("API 응답:", r.status_code, r.text[:200])


def send_gas(cfg: dict, to: list[str], cc: list[str], subject: str, html_: str, d: dict) -> None:
    """사내 Apps Script(공수 시스템 등)에 있는 기존 다우오피스 발송 로직을 재사용한다.
    Apps Script 쪽에 아래 형태의 action 하나만 추가하면 된다(수신자·제목·본문을 받아 기존 발송 함수로 넘김).
        {action:"sendBrief", token:"...", to:[...], cc:[...], subject:"...", html:"..."}"""
    import requests
    url = os.environ.get("GAS_URL") or cfg.get("url", "")
    token = os.environ.get("GAS_TOKEN", "")
    if not url:
        raise SystemExit("GAS_URL 환경 변수(GitHub Secrets)가 없습니다.")
    payload = {"action": cfg.get("action", "sendBrief"), "token": token,
               "to": to, "cc": cc, "subject": subject, "html": html_,
               "date": d.get("date", ""), "issue_no": d.get("issue_no", 0), "url": SITE_URL}
    r = requests.post(url, json=payload, timeout=60, allow_redirects=True)
    if r.status_code >= 300:
        raise SystemExit(f"Apps Script 응답 {r.status_code}: {r.text[:300]}")
    print("Apps Script 응답:", r.status_code, r.text[:200])


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    day = args[0] if args else datetime.now(tz=KST).strftime("%Y-%m-%d")
    f = DATA / f"{day}.json"
    if not f.exists():
        print(f"발행 데이터 없음: {f}"); return 1
    d = json.loads(f.read_text(encoding="utf-8"))
    wl = B.load_watchlist()
    cfg = wl.get("mail") or {}
    if not cfg.get("enabled", False) and not dry:
        print("mail.enabled 가 false 라 보내지 않습니다."); return 0
    to = [x for x in (os.environ.get("MAIL_TO", "").split(",") if os.environ.get("MAIL_TO") else (cfg.get("to") or [])) if x.strip()]
    cc = [x for x in (cfg.get("cc") or []) if x.strip()]
    subject, html_ = build_html(d, wl)
    if cfg.get("subject_prefix"):
        subject = f'{cfg["subject_prefix"]} {subject}'
    if dry:
        out = B.ROOT / "out"; out.mkdir(exist_ok=True)
        (out / f"mail-{day}.html").write_text(html_, encoding="utf-8")
        print(f"[dry-run] 제목: {subject}\n[dry-run] 수신: {to} cc: {cc}\n[dry-run] 본문 저장: out/mail-{day}.html"); return 0
    if not to:
        print("수신자(mail.to)가 비어 있어 보내지 않습니다."); return 0
    mode = (cfg.get("mode") or "gas").lower()
    if mode == "gas":
        send_gas(cfg.get("gas") or {}, to, cc, subject, html_, d)
    elif mode == "api":
        send_api(cfg.get("api") or {}, to, cc, subject, html_, d)
    else:
        send_smtp(cfg.get("smtp") or {}, to, cc, subject, html_)
    print(f"발송 완료({mode}): {subject} → {len(to)}명 (cc {len(cc)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
