const apiPrefix = '/api';
let currentSessionId = null;

const candidateIdEl = document.getElementById('candidateId');
const candidateRoleEl = document.getElementById('candidateRole');
const candidateLanguageEl = document.getElementById('candidateLanguage');
const createSessionBtn = document.getElementById('createSessionBtn');
const sessionStatusEl = document.getElementById('sessionStatus');

const eventTypeEl = document.getElementById('eventType');
const candidateMessageEl = document.getElementById('candidateMessage');
const codeDeltaEl = document.getElementById('codeDelta');
const heartRateEl = document.getElementById('heartRate');
const stressIndexEl = document.getElementById('stressIndex');
const silenceMsEl = document.getElementById('silenceMs');
const sendEventBtn = document.getElementById('sendEventBtn');
const eventStatusEl = document.getElementById('eventStatus');
const cameraPreviewEl = document.getElementById('cameraPreview');
const startCameraBtn = document.getElementById('startCameraBtn');
const captureFrameBtn = document.getElementById('captureFrameBtn');
const toggleAutoCaptureBtn = document.getElementById('toggleAutoCaptureBtn');
const captureStatusEl = document.getElementById('captureStatus');

const traceListEl = document.getElementById('traceList');
const traceStatusEl = document.getElementById('traceStatus');
const refreshTraceBtn = document.getElementById('refreshTraceBtn');

const statSessionEl = document.getElementById('statSession');
const statScoreEl = document.getElementById('statScore');
const statStressEl = document.getElementById('statStress');
const statLifecycleEl = document.getElementById('statLifecycle');
const statEventsEl = document.getElementById('statEvents');
const statRouteEl = document.getElementById('statRoute');
const sessionMetaEl = document.getElementById('sessionMeta');

const finalizeNoteEl = document.getElementById('finalizeNote');
const finalizeSessionBtn = document.getElementById('finalizeSessionBtn');
const finalizeStatusEl = document.getElementById('finalizeStatus');
const reviewerIdEl = document.getElementById('reviewerId');
const reviewDecisionEl = document.getElementById('reviewDecision');
const reviewRationaleEl = document.getElementById('reviewRationale');
const submitReviewBtn = document.getElementById('submitReviewBtn');
const reviewStatusEl = document.getElementById('reviewStatus');

const refreshObservabilityBtn = document.getElementById('refreshObservabilityBtn');
const observabilityStatusEl = document.getElementById('observabilityStatus');
const observabilityBoxEl = document.getElementById('observabilityBox');

const refreshReportBtn = document.getElementById('refreshReportBtn');
const reportStatusEl = document.getElementById('reportStatus');
const reportBoxEl = document.getElementById('reportBox');
const livePromptEl = document.getElementById('livePrompt');
const askLiveBtn = document.getElementById('askLiveBtn');
const startVoiceBtn = document.getElementById('startVoiceBtn');
const stopVoiceBtn = document.getElementById('stopVoiceBtn');
const liveStatusEl = document.getElementById('liveStatus');
const liveResponseBoxEl = document.getElementById('liveResponseBox');

const agentCardsBoxEl = document.getElementById('agentCardsBox');
const requesterAgentIdEl = document.getElementById('requesterAgentId');
const targetAgentIdEl = document.getElementById('targetAgentId');
const requestedCapabilitiesEl = document.getElementById('requestedCapabilities');
const handshakeBtn = document.getElementById('handshakeBtn');
const handshakeStatusEl = document.getElementById('handshakeStatus');
const handshakeBoxEl = document.getElementById('handshakeBox');

const phaseTableBodyEl = document.getElementById('phaseTableBody');
const revPhaseIdEl = document.getElementById('revPhaseId');
const revStatusEl = document.getElementById('revStatus');
const revSummaryEl = document.getElementById('revSummary');
const revReasonEl = document.getElementById('revReason');
const revisePhaseBtn = document.getElementById('revisePhaseBtn');
const phaseStatusEl = document.getElementById('phaseStatus');
let cameraStream = null;
let autoCaptureTimer = null;
let speechRecognition = null;
let sessionSocket = null;
let sessionSocketPing = null;

createSessionBtn.addEventListener('click', createSession);
sendEventBtn.addEventListener('click', ingestEvent);
refreshTraceBtn.addEventListener('click', refreshTrace);
revisePhaseBtn.addEventListener('click', revisePhase);
finalizeSessionBtn.addEventListener('click', finalizeSession);
submitReviewBtn.addEventListener('click', submitHumanReview);
refreshObservabilityBtn.addEventListener('click', refreshObservability);
refreshReportBtn.addEventListener('click', refreshReport);
startCameraBtn.addEventListener('click', startCamera);
captureFrameBtn.addEventListener('click', captureAndSendFrame);
toggleAutoCaptureBtn.addEventListener('click', toggleAutoCapture);
askLiveBtn.addEventListener('click', () => askLiveResponse('text'));
startVoiceBtn.addEventListener('click', startVoiceRecognition);
stopVoiceBtn.addEventListener('click', stopVoiceRecognition);
handshakeBtn.addEventListener('click', runHandshake);

async function createSession() {
  setStatus(sessionStatusEl, 'Creating session...', 'ok');

  const payload = {
    candidate_id: candidateIdEl.value.trim(),
    candidate_role: candidateRoleEl.value.trim(),
    language: candidateLanguageEl.value.trim() || 'en',
  };

  try {
    const session = await request(`${apiPrefix}/sessions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    currentSessionId = session.session_id;
    connectSessionStream();
    applySnapshot(session);
    setStatus(sessionStatusEl, `Session active: ${currentSessionId}`, 'ok');
    await refreshAll();
  } catch (error) {
    setStatus(sessionStatusEl, `Create failed: ${error.message}`, 'err');
  }
}

async function ingestEvent() {
  if (!currentSessionId) {
    setStatus(eventStatusEl, 'Create a session first.', 'err');
    return;
  }

  setStatus(eventStatusEl, 'Executing graph loop...', 'ok');

  const payload = {
    event_type: eventTypeEl.value,
    telemetry: {
      candidate_message: candidateMessageEl.value.trim() || null,
      audio_text: candidateMessageEl.value.trim() || null,
      code_delta: codeDeltaEl.value.trim() || null,
      heart_rate_bpm: numberOrNull(heartRateEl.value),
      stress_index: numberOrNull(stressIndexEl.value),
      silence_ms: numberOrDefault(silenceMsEl.value, 0),
      raw_vector_hash: '6f1f4dc566f90f5ecf98ee4f710a9f8c',
    },
    raw_payload: {
      wallet_address: 'did:key:z6Mkq1SecureDemoKey',
    },
  };

  try {
    const snapshot = await request(`${apiPrefix}/sessions/${currentSessionId}/events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    applySnapshot(snapshot);
    setStatus(eventStatusEl, 'ReAct cycle completed.', 'ok');
    await refreshAll();
  } catch (error) {
    setStatus(eventStatusEl, `Execution failed: ${error.message}`, 'err');
  }
}

async function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setStatus(captureStatusEl, 'Camera API is not available in this browser.', 'err');
    return;
  }

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 960 },
        height: { ideal: 540 },
        facingMode: 'user',
      },
      audio: false,
    });
    cameraPreviewEl.srcObject = cameraStream;
    toggleAutoCaptureBtn.disabled = !currentSessionId;
    setStatus(captureStatusEl, 'Camera active.', 'ok');
  } catch (error) {
    setStatus(captureStatusEl, `Camera start failed: ${error.message}`, 'err');
  }
}

async function captureAndSendFrame() {
  if (!currentSessionId) {
    setStatus(captureStatusEl, 'Create a session first.', 'err');
    return;
  }
  if (!cameraStream) {
    setStatus(captureStatusEl, 'Start the camera first.', 'err');
    return;
  }

  try {
    const frame = captureVideoFrame(cameraPreviewEl);
    const hash = await sha256Hex(frame);
    const payload = {
      event_type: 'webcam_frame',
      telemetry: {
        silence_ms: 0,
        raw_vector_hash: hash.slice(0, 64),
      },
      raw_payload: {
        video_frame: frame,
      },
    };

    const snapshot = await request(`${apiPrefix}/sessions/${currentSessionId}/events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    applySnapshot(snapshot);
    setStatus(captureStatusEl, 'Frame sent and enriched with rPPG pulse.', 'ok');
    await refreshAll();
  } catch (error) {
    setStatus(captureStatusEl, `Frame send failed: ${error.message}`, 'err');
  }
}

function toggleAutoCapture() {
  if (autoCaptureTimer) {
    clearInterval(autoCaptureTimer);
    autoCaptureTimer = null;
    toggleAutoCaptureBtn.textContent = 'Auto Capture Off';
    setStatus(captureStatusEl, 'Auto capture stopped.', 'ok');
    return;
  }

  autoCaptureTimer = setInterval(() => {
    if (currentSessionId && cameraStream) {
      captureAndSendFrame();
    }
  }, 5000);
  toggleAutoCaptureBtn.textContent = 'Auto Capture On';
  setStatus(captureStatusEl, 'Auto capture started at 5s interval.', 'ok');
}

async function askLiveResponse(channel = 'text') {
  if (!currentSessionId) {
    setStatus(liveStatusEl, 'Create a session first.', 'err');
    return;
  }

  setStatus(liveStatusEl, 'Generating live response...', 'ok');

  try {
    const response = await request(`${apiPrefix}/sessions/${currentSessionId}/live-response`, {
      method: 'POST',
      body: JSON.stringify({
        prompt: livePromptEl.value.trim(),
        locale: candidateLanguageEl.value.trim() || 'en',
        channel,
      }),
    });
    liveResponseBoxEl.innerHTML = `
      <div class="detail-section">
        <div><strong>Channel:</strong> ${escapeHtml(response.channel)}</div>
        <div><strong>Tier:</strong> ${escapeHtml(response.target_tier)}</div>
        <div><strong>Safe:</strong> ${response.safe_for_candidate}</div>
      </div>
      <div class="detail-section">
        <div>${escapeHtml(response.response_text)}</div>
      </div>
      <div class="detail-section">
        <div class="chip-row">${(response.hints_used || [])
          .map((hint) => `<span class="chip">${escapeHtml(hint)}</span>`)
          .join('')}</div>
      </div>
    `;
    setStatus(liveStatusEl, 'Live response generated.', 'ok');
    if (channel === 'voice' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(response.response_text));
    }
  } catch (error) {
    setStatus(liveStatusEl, `Live response failed: ${error.message}`, 'err');
  }
}

function startVoiceRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    setStatus(liveStatusEl, 'Browser speech recognition is not available.', 'err');
    return;
  }
  if (!currentSessionId) {
    setStatus(liveStatusEl, 'Create a session first.', 'err');
    return;
  }

  speechRecognition = new Recognition();
  speechRecognition.lang = candidateLanguageEl.value.trim() || 'en-US';
  speechRecognition.continuous = true;
  speechRecognition.interimResults = false;
  speechRecognition.onresult = async (event) => {
    const transcript = Array.from(event.results)
      .slice(event.resultIndex)
      .map((result) => result[0].transcript)
      .join(' ')
      .trim();
    if (!transcript) {
      return;
    }
    livePromptEl.value = transcript;
    await askLiveResponse('voice');
  };
  speechRecognition.onerror = (event) => {
    setStatus(liveStatusEl, `Voice recognition error: ${event.error}`, 'err');
  };
  speechRecognition.onend = () => {
    startVoiceBtn.disabled = false;
    stopVoiceBtn.disabled = true;
  };
  speechRecognition.start();
  startVoiceBtn.disabled = true;
  stopVoiceBtn.disabled = false;
  setStatus(liveStatusEl, 'Voice recognition active.', 'ok');
}

function stopVoiceRecognition() {
  if (speechRecognition) {
    speechRecognition.stop();
    speechRecognition = null;
  }
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  startVoiceBtn.disabled = false;
  stopVoiceBtn.disabled = true;
  setStatus(liveStatusEl, 'Voice recognition stopped.', 'ok');
}

async function runHandshake() {
  const requestedCapabilities = requestedCapabilitiesEl.value
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  try {
    const response = await request(`${apiPrefix}/a2a/handshake`, {
      method: 'POST',
      body: JSON.stringify({
        requester_agent_id: requesterAgentIdEl.value,
        target_agent_id: targetAgentIdEl.value,
        requested_capabilities: requestedCapabilities,
        nonce: crypto.randomUUID(),
        session_id: currentSessionId,
      }),
    });
    handshakeBoxEl.innerHTML = `
      <div class="detail-section">
        <div><strong>Accepted:</strong> ${response.accepted}</div>
        <div><strong>Reason:</strong> ${escapeHtml(response.reason)}</div>
      </div>
      <div class="detail-section">
        <div><strong>Token:</strong> <span class="mono">${escapeHtml(response.handshake_token || '-')}</span></div>
        <div class="chip-row">${(response.approved_capabilities || [])
          .map((capability) => `<span class="chip">${escapeHtml(capability)}</span>`)
          .join('')}</div>
      </div>
    `;
    setStatus(
      handshakeStatusEl,
      response.accepted ? 'Handshake accepted.' : 'Handshake rejected.',
      response.accepted ? 'ok' : 'err'
    );
  } catch (error) {
    setStatus(handshakeStatusEl, `Handshake failed: ${error.message}`, 'err');
  }
}

async function finalizeSession() {
  if (!currentSessionId) {
    setStatus(finalizeStatusEl, 'Create a session first.', 'err');
    return;
  }

  setStatus(finalizeStatusEl, 'Generating evidence package...', 'ok');

  try {
    const report = await request(`${apiPrefix}/sessions/${currentSessionId}/finalize`, {
      method: 'POST',
      body: JSON.stringify({
        summary_note: finalizeNoteEl.value.trim() || null,
        force: false,
      }),
    });
    renderReport(report);
    setStatus(finalizeStatusEl, 'Session finalized and sent to human review.', 'ok');
    await refreshAll();
  } catch (error) {
    setStatus(finalizeStatusEl, `Finalize failed: ${error.message}`, 'err');
  }
}

async function submitHumanReview() {
  if (!currentSessionId) {
    setStatus(reviewStatusEl, 'Create a session first.', 'err');
    return;
  }

  setStatus(reviewStatusEl, 'Applying human decision...', 'ok');

  try {
    const review = await request(`${apiPrefix}/sessions/${currentSessionId}/human-review`, {
      method: 'POST',
      body: JSON.stringify({
        reviewer_id: reviewerIdEl.value.trim(),
        decision: reviewDecisionEl.value,
        rationale: reviewRationaleEl.value.trim(),
        cryptographic_acknowledgement: true,
      }),
    });
    setStatus(
      reviewStatusEl,
      `Human decision recorded: ${review.decision} by ${review.reviewer_id}.`,
      'ok'
    );
    await refreshAll();
  } catch (error) {
    setStatus(reviewStatusEl, `Review failed: ${error.message}`, 'err');
  }
}

async function refreshAll() {
  if (!currentSessionId) {
    return;
  }

  await Promise.allSettled([
    refreshSession(),
    refreshTrace(),
    refreshReport(),
    refreshObservability(),
  ]);
}

async function refreshSession() {
  if (!currentSessionId) {
    return;
  }

  const snapshot = await request(`${apiPrefix}/sessions/${currentSessionId}`);
  applySnapshot(snapshot);
}

async function refreshTrace() {
  if (!currentSessionId) {
    traceListEl.innerHTML = '<div class="trace-item">No active session.</div>';
    return;
  }

  setStatus(traceStatusEl, 'Refreshing trace...', 'ok');

  try {
    const traces = await request(`${apiPrefix}/sessions/${currentSessionId}/trace?limit=100`);
    renderTrace(traces);
    setStatus(traceStatusEl, `Trace events: ${traces.length}`, 'ok');
  } catch (error) {
    setStatus(traceStatusEl, `Trace fetch failed: ${error.message}`, 'err');
  }
}

async function refreshReport() {
  if (!currentSessionId) {
    reportBoxEl.textContent = 'No report loaded.';
    return;
  }

  setStatus(reportStatusEl, 'Refreshing report...', 'ok');

  try {
    const report = await request(`${apiPrefix}/sessions/${currentSessionId}/glass-box`);
    renderReport(report);
    setStatus(reportStatusEl, `Recommendation: ${report.recommendation}`, 'ok');
  } catch (error) {
    setStatus(reportStatusEl, `Report load failed: ${error.message}`, 'err');
  }
}

async function refreshObservability() {
  if (!currentSessionId) {
    observabilityBoxEl.textContent = 'No observability snapshot yet.';
    return;
  }

  setStatus(observabilityStatusEl, 'Refreshing observability...', 'ok');

  try {
    const snapshot = await request(`${apiPrefix}/sessions/${currentSessionId}/observability`);
    renderObservability(snapshot);
    setStatus(observabilityStatusEl, 'Observability snapshot loaded.', 'ok');
  } catch (error) {
    setStatus(observabilityStatusEl, `Observability failed: ${error.message}`, 'err');
  }
}

async function refreshPhases() {
  try {
    const phases = await request(`${apiPrefix}/phases`);
    renderPhases(phases);
  } catch (error) {
    phaseTableBodyEl.innerHTML =
      `<tr><td colspan="5">Phase load failed: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function revisePhase() {
  const phaseId = Number.parseInt(revPhaseIdEl.value, 10);
  if (!phaseId || phaseId < 1 || phaseId > 15) {
    setStatus(phaseStatusEl, 'Phase ID must be between 1 and 15.', 'err');
    return;
  }

  const payload = {
    status: revStatusEl.value,
    summary: revSummaryEl.value.trim(),
    rationale: revReasonEl.value.trim(),
  };

  try {
    const revision = await request(`${apiPrefix}/phases/${phaseId}/revisions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setStatus(
      phaseStatusEl,
      `Phase ${revision.phase_id} revised at ${new Date(revision.revised_at_utc).toLocaleString()}`,
      'ok'
    );
    await refreshPhases();
  } catch (error) {
    setStatus(phaseStatusEl, `Revision failed: ${error.message}`, 'err');
  }
}

async function loadAgentCards() {
  try {
    const cards = await request(`${apiPrefix}/agent-cards`);
    renderAgentCards(cards);
  } catch (error) {
    agentCardsBoxEl.textContent = `Agent card load failed: ${error.message}`;
  }
}

function connectSessionStream() {
  if (!currentSessionId) {
    return;
  }
  if (sessionSocket) {
    sessionSocket.close();
  }

  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  sessionSocket = new WebSocket(
    `${scheme}://${window.location.host}${apiPrefix}/sessions/${currentSessionId}/ws`
  );

  sessionSocket.onopen = () => {
    sessionSocket.send('hello');
    if (sessionSocketPing) {
      clearInterval(sessionSocketPing);
    }
    sessionSocketPing = setInterval(() => {
      if (sessionSocket && sessionSocket.readyState === WebSocket.OPEN) {
        sessionSocket.send('ping');
      }
    }, 15000);
  };

  sessionSocket.onmessage = async () => {
    await refreshAll();
  };

  sessionSocket.onclose = () => {
    if (sessionSocketPing) {
      clearInterval(sessionSocketPing);
      sessionSocketPing = null;
    }
  };
}

function renderTrace(traces) {
  if (!traces.length) {
    traceListEl.innerHTML = '<div class="trace-item">No trace events yet.</div>';
    return;
  }

  traceListEl.innerHTML = traces
    .map((trace) => {
      const ts = new Date(trace.completed_at_utc).toLocaleTimeString();
      const attrs = renderChips(trace.attributes || {});
      return `
        <div class="trace-item">
          <div><span class="trace-node">${escapeHtml(trace.node)}</span> <strong>${trace.latency_ms}ms</strong> <span>${escapeHtml(ts)}</span></div>
          <div>${escapeHtml(trace.reasoning_path)}</div>
          <div class="inline-note">${escapeHtml(trace.input_contract)} -> ${escapeHtml(trace.output_contract)}</div>
          ${attrs}
        </div>
      `;
    })
    .join('');
}

function renderPhases(phases) {
  phaseTableBodyEl.innerHTML = phases
    .map((phase) => {
      return `
        <tr>
          <td>${phase.phase_id}</td>
          <td>${escapeHtml(phase.title)}</td>
          <td>${escapeHtml(phase.owner_framework)}</td>
          <td>${escapeHtml(phase.objective)}</td>
          <td><span class="phase-pill ${escapeHtml(phase.status)}">${escapeHtml(phase.status)}</span></td>
        </tr>
      `;
    })
    .join('');
}

function renderReport(report) {
  const evidence = report.evidence
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join('');
  const mapEdges = (report.reasoning_map.graph_edges || [])
    .slice(0, 4)
    .map((edge) => `<div><code>${escapeHtml(edge.from)}</code> -> <code>${escapeHtml(edge.to)}</code> ${escapeHtml(edge.label)}</div>`)
    .join('');

  reportBoxEl.innerHTML = `
    <div class="detail-section">
      <div><strong>Recommendation:</strong> ${escapeHtml(report.recommendation)}</div>
      <div><strong>Final score:</strong> ${Number(report.final_score).toFixed(2)}</div>
      <div><strong>Human approval required:</strong> ${report.human_approval_required}</div>
      <div><strong>Trace count:</strong> ${report.trace_count}</div>
    </div>
    <div class="detail-section">
      <div><strong>Consensus:</strong> ${escapeHtml(report.consensus_summary)}</div>
      <div><strong>Candidate-safe summary:</strong> ${escapeHtml(report.candidate_safe_summary)}</div>
      <div><strong>EEOC explanation:</strong> ${escapeHtml(report.eeoc_explanation)}</div>
    </div>
    <div class="detail-section">
      <div><strong>Evidence</strong></div>
      <div class="chip-row">${evidence || '<span class="chip">No evidence</span>'}</div>
    </div>
    <div class="detail-section">
      <div><strong>Reasoning map</strong></div>
      <div>Nodes: ${escapeHtml(report.reasoning_map.graph_nodes || 0)}</div>
      ${mapEdges || '<div>No graph edges yet.</div>'}
    </div>
  `;
}

function renderObservability(snapshot) {
  const breakdown = Object.entries(snapshot.node_breakdown || {})
    .map(([key, value]) => `<span class="chip">${escapeHtml(key)}: ${escapeHtml(value)}</span>`)
    .join('');
  const drifts = (snapshot.drift_flags || [])
    .map((flag) => `<span class="chip">${escapeHtml(flag)}</span>`)
    .join('');

  observabilityBoxEl.innerHTML = `
    <div class="detail-section">
      <div><strong>Status:</strong> ${escapeHtml(snapshot.session_status)}</div>
      <div><strong>Total traces:</strong> ${snapshot.total_traces}</div>
      <div><strong>Average latency:</strong> ${Number(snapshot.average_latency_ms).toFixed(2)}ms</div>
      <div><strong>Estimated tokens saved:</strong> ${snapshot.estimated_tokens_saved}</div>
      <div><strong>Latest score:</strong> ${Number(snapshot.latest_score).toFixed(2)}</div>
    </div>
    <div class="detail-section">
      <div><strong>Node breakdown</strong></div>
      <div class="chip-row">${breakdown || '<span class="chip">No nodes</span>'}</div>
    </div>
    <div class="detail-section">
      <div><strong>Drift flags</strong></div>
      <div class="chip-row">${drifts || '<span class="chip">none</span>'}</div>
      <div><strong>Cost governor:</strong> ${escapeHtml(snapshot.cost_governor_recommendation)}</div>
    </div>
  `;
}

function renderAgentCards(cards) {
  agentCardsBoxEl.innerHTML = `
    <div class="agent-grid">
      ${cards
        .map((card) => {
          const capabilities = card.capabilities
            .map((capability) => `<span class="chip">${escapeHtml(capability)}</span>`)
            .join('');
          return `
            <div class="agent-card">
              <h3>${escapeHtml(card.agent_name)}</h3>
              <div><strong>Protocol:</strong> ${escapeHtml(card.protocol_version)}</div>
              <div><strong>Tier:</strong> ${escapeHtml(card.model_tier)}</div>
              <div><strong>Agent ID:</strong> <span class="mono">${escapeHtml(card.agent_id)}</span></div>
              <div><strong>Fingerprint:</strong> <span class="mono">${escapeHtml(card.public_key_fingerprint)}</span></div>
              <div class="chip-row">${capabilities}</div>
            </div>
          `;
        })
        .join('')}
    </div>
  `;
}

function renderChips(attributes) {
  const entries = Object.entries(attributes || {});
  if (!entries.length) {
    return '';
  }

  const chips = entries
    .map(([key, value]) => `<span class="chip">${escapeHtml(key)}: ${escapeHtml(value)}</span>`)
    .join('');
  return `<div class="chip-row">${chips}</div>`;
}

function applySnapshot(snapshot) {
  statSessionEl.textContent = snapshot.session_id.slice(0, 8);
  statScoreEl.textContent = Number(snapshot.candidate_score).toFixed(2);
  statStressEl.textContent = Number(snapshot.current_stress_level).toFixed(2);
  statLifecycleEl.textContent = snapshot.session_status;
  statEventsEl.textContent = String(snapshot.event_count);
  statRouteEl.textContent = snapshot.last_route_target || '-';

  const recommendation = snapshot.latest_recommendation || 'n/a';
  const decision = snapshot.human_decision || 'n/a';
  sessionMetaEl.textContent =
    `Recommendation: ${recommendation}. Human decision: ${decision}. ` +
    `Completed at: ${snapshot.completed_at_utc ? new Date(snapshot.completed_at_utc).toLocaleString() : 'not finalized'}.`;

  const locked = ['review_pending', 'approved', 'rejected'].includes(snapshot.session_status);
  if (locked && autoCaptureTimer) {
    clearInterval(autoCaptureTimer);
    autoCaptureTimer = null;
    toggleAutoCaptureBtn.textContent = 'Auto Capture Off';
  }
  sendEventBtn.disabled = locked;
  finalizeSessionBtn.disabled = !currentSessionId || snapshot.event_count === 0 || locked;
  submitReviewBtn.disabled = !currentSessionId || !snapshot.report_available;
  captureFrameBtn.disabled = !currentSessionId || locked;
  askLiveBtn.disabled = !currentSessionId;
  startVoiceBtn.disabled = !currentSessionId || speechRecognition !== null;
  stopVoiceBtn.disabled = speechRecognition === null;
  toggleAutoCaptureBtn.disabled = !currentSessionId || !cameraStream || locked;
}

function setStatus(target, text, mode) {
  target.textContent = text;
  target.className = `status ${mode}`;
}

function numberOrNull(value) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function numberOrDefault(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function captureVideoFrame(videoEl) {
  const canvas = document.createElement('canvas');
  canvas.width = videoEl.videoWidth || 640;
  canvas.height = videoEl.videoHeight || 360;
  const context = canvas.getContext('2d');
  context.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.82);
}

async function sha256Hex(value) {
  const encoder = new TextEncoder();
  const bytes = encoder.encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail || text;
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

refreshPhases();
loadAgentCards();
setInterval(() => {
  if (currentSessionId) {
    refreshAll();
  }
}, 7000);
