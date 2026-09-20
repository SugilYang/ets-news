/**
 * 이티에스 시장 동향 — 발행 메일 중계 (기존 공수 시스템 Apps Script 에 붙여 넣는 코드)
 *
 * 왜 이렇게 하나: 다우오피스로 메일·알림을 보내는 코드가 이미 그 Apps Script 안에 있으니,
 * ets-news 는 "이 내용을 이 사람들에게 보내 달라"고 부르기만 하면 됩니다. 계정 정보를 한 곳에만 둡니다.
 *
 * ── 붙이는 방법 ─────────────────────────────────────────────────────
 * 1) 공수 시스템 Apps Script 편집기를 열고 아래 두 가지를 넣습니다.
 *    (가) 아래 sendBrief_ 함수 전체를 파일 맨 아래에 붙여넣기
 *    (나) doPost(e) 안의 action 분기(switch/if)에 한 줄 추가:
 *           if (req.action === 'sendBrief') return sendBrief_(req);
 *         ※ 기존 코드가 `switch(action)` 이면  case 'sendBrief': return sendBrief_(req);
 * 2) 편집기 왼쪽 ⚙ 프로젝트 설정 → 스크립트 속성에 BRIEF_TOKEN 을 만들고 아무 암호나 넣습니다.
 *    (예: ets-brief-2026-x9f2)  ← 이 값을 GitHub Secrets 의 GAS_TOKEN 에도 똑같이 넣습니다.
 * 3) 배포 → 새 배포(또는 기존 배포 관리 → 버전 새로 만들기). 웹앱 주소를 GitHub Secrets 의 GAS_URL 에 넣습니다.
 *    (액세스 권한: "모든 사용자" — 토큰으로 막으므로 안전합니다)
 *
 * ── 다우오피스 발송 함수 연결 ────────────────────────────────────────
 * 아래 SEND 부분에서 기존에 쓰던 발송 함수를 호출하도록 한 줄만 바꾸면 됩니다.
 *   예) 금요일 미입력 알림에 쓰는 함수가 sendDaouMail_(to, subject, html) 이라면
 *       sendDaouMail_(to.join(','), subject, html);
 * 기존 함수 이름을 모르면 그대로 두세요. 기본값은 Apps Script 기본 메일(MailApp)로 나갑니다.
 */
function sendBrief_(req) {
  var out = function (obj) {
    return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
  };
  try {
    var want = PropertiesService.getScriptProperties().getProperty('BRIEF_TOKEN') || '';
    if (!want || String(req.token || '') !== want) return out({ ok: false, msg: '토큰 불일치' });

    var to = [].concat(req.to || []).filter(String);
    var cc = [].concat(req.cc || []).filter(String);
    if (!to.length) return out({ ok: false, msg: '수신자 없음' });

    var subject = String(req.subject || '이티에스 시장 동향');
    var html = String(req.html || '');

    // ── SEND ── 기존 다우오피스 발송 함수가 있으면 이 줄을 그것으로 바꾸세요.
    MailApp.sendEmail({
      to: to.join(','),
      cc: cc.join(','),
      subject: subject,
      htmlBody: html,
      name: '이티에스 시장 동향',
      noReply: true
    });

    return out({ ok: true, msg: '발송 ' + to.length + '명', date: req.date || '', issue: req.issue_no || 0 });
  } catch (err) {
    return out({ ok: false, msg: String(err) });
  }
}
