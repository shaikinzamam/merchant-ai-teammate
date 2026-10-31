import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { makeApi } from './api.js'

const MERCHANTS = [
  ['M1001', 'Ramesh · Hindi (delayed settlement)'],
  ['M1002', 'Lakshmi · Telugu'],
  ['M1003', 'Fraud-flagged → escalates'],
  ['M1004', 'KYC failures → escalates'],
  ['M1005', 'High volume → EDC lead'],
]
const SAMPLES = [
  'Mera kal ka settlement abhi tak account me kyu nahi aaya?',
  'I want to raise a dispute for TXN100001, double debit',
  'My soundbox is not working, please send a technician',
  'Someone hacked my account, unauthorized transfers',
]
const VOICE_PROMPTS = [
  { label: 'Hindi · settlement', merchant: 'M1001', text: 'मेरा कल का सेटलमेंट अभी तक खाते में क्यों नहीं आया?' },
  { label: 'తెలుగు · settlement', merchant: 'M1002', text: 'నా సెటిల్‌మెంట్ ఇంకా నా ఖాతాలోకి ఎందుకు రాలేదు?' },
  { label: 'Dispute · double debit', merchant: 'M1001', text: 'I want to raise a dispute for TXN100001, double debit.' },
]
const EMPTY_CREDS = { serviceKey: '', opId: 'op-demo', opKey: '' }
const BACKEND_UNREACHABLE_MESSAGE = 'Backend not reachable. Start the API on port 8000.'
const LANGUAGE_NAMES = { en: 'English', hi: 'Hindi', te: 'Telugu', kn: 'Kannada' }
const apiErrorMessage = error =>
  error?.status === 404
    ? 'Feature not available on this backend.'
    : !Number.isInteger(error?.status) || error.status >= 500
    ? BACKEND_UNREACHABLE_MESSAGE
    : error.message
const credentialStrings = value => ({
  serviceKey: typeof value?.serviceKey === 'string' ? value.serviceKey : '',
  opId: typeof value?.opId === 'string' ? value.opId : EMPTY_CREDS.opId,
  opKey: typeof value?.opKey === 'string' ? value.opKey : '',
})
const load = () => {
  try { return credentialStrings(JSON.parse(sessionStorage.getItem('creds') || '{}')) }
  catch { return EMPTY_CREDS }
}

const Chip = ({ status }) => <span className={`chip ${status}`}>{status.replace('_', ' ')}</span>

function Credentials({ creds, setCreds, operatorVerified, onVerify, serviceKeyConfigured }) {
  const set = k => e => setCreds({ ...creds, [k]: e.target.value })
  const clear = () => { sessionStorage.removeItem('creds'); setCreds(EMPTY_CREDS) }
  const serviceReady = Boolean(creds.serviceKey.trim())
  const serviceWhitespaceOnly = Boolean(creds.serviceKey) && !serviceReady
  const operatorReady = Boolean(creds.opId.trim() && creds.opKey.trim())
  return (
    <details className="card credentials" open>
      <summary>API credentials (kept in this tab only)</summary>
      <div className="row">
        <input type="password" aria-label="Service API key" placeholder="SERVICE_API_KEY" value={creds.serviceKey} onChange={set('serviceKey')} />
        <input aria-label="Operator ID from OPERATOR_API_KEYS" placeholder="Operator ID" value={creds.opId} onChange={set('opId')} />
        <input type="password" aria-label="Operator key from OPERATOR_API_KEYS" placeholder="Operator key" value={creds.opKey} onChange={set('opKey')} />
      </div>
      <div className="credential-status">
        <span className={serviceReady ? 'ok' : 'muted'}>Merchant API: {serviceReady ? 'ready to send from this tab' : serviceWhitespaceOnly ? 'key contains only whitespace' : 'SERVICE_API_KEY required'}</span>
        {serviceKeyConfigured != null && <span className={serviceKeyConfigured ? 'ok' : 'muted'}>Backend service key: {serviceKeyConfigured ? 'configured' : 'missing'}</span>}
        <span className={operatorVerified ? 'ok' : 'muted'}>Operator: {operatorVerified ? `verified as ${operatorVerified}` : operatorReady ? 'ready to verify' : 'OPERATOR_API_KEYS ID and key required'}</span>
        <button className="ghost compact" disabled={!operatorReady} onClick={onVerify}>Verify operator</button>
        <button className="link-button" onClick={clear}>Clear keys</button>
      </div>
      <p className="muted small">
        Configure <code>SERVICE_API_KEY</code> in the project root <code>.env</code>, then enter its value here for merchant chat.
        Configure <code>OPERATOR_API_KEYS</code> there as a JSON map (for example <code>{'{"op-demo":"your-key"}'}</code>);
        enter the map key as the operator ID and its value as the operator key. The server never sends these secrets to the browser.
        Entered keys are stored only in this browser tab.
      </p>
    </details>
  )
}

function Chat({ api, onServiceAuthFailure, voiceEnabled, voiceStatusError }) {
  const [merchant, setMerchant] = useState('M1001')
  const [text, setText] = useState('')
  const [log, setLog] = useState([])
  const [session, setSession] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [recording, setRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [activePrompt, setActivePrompt] = useState('')
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])

  const pick = id => { setMerchant(id); setSession(null); setLog([]); setErr('') }
  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }, [])

  useEffect(() => {
    if (!recording) return undefined
    const startedAt = Date.now()
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000)
      setRecordingSeconds(elapsed)
      if (elapsed >= 30) stopRecording()
    }, 250)
    return () => clearInterval(timer)
  }, [recording, stopRecording])

  useEffect(() => () => {
    if (recorderRef.current?.state !== 'inactive') recorderRef.current?.stop()
    streamRef.current?.getTracks().forEach(track => track.stop())
  }, [])

  const sendVoice = async (audio, merchantId, sessionId) => {
    if (!api.hasServiceCredentials()) {
      setErr('Enter the configured SERVICE_API_KEY in API credentials before using voice.')
      return
    }
    setBusy(true); setErr('')
    try {
      const response = await api.voiceChat(merchantId, audio, sessionId)
      setSession(response.session_id)
      setLog(items => [
        ...items,
        ...(response.transcript ? [{ me: true, text: response.transcript }] : []),
        {
          text: response.reply,
          actions: response.actions,
          meta: `${response.language} · ${response.intent} · planner: ${response.planner}`,
          detectedLanguage: response.detected_language || response.language,
          audio: response.audio,
        },
      ])
      setActivePrompt('')
    } catch (error) {
      if (error.status === 401) {
        onServiceAuthFailure()
        setErr('The merchant API key saved in this tab was rejected. It has been cleared; enter the exact current SERVICE_API_KEY and try again.')
      } else if (error.status === 501) {
        setErr('Voice is not enabled on this backend. You can still type a message.')
      } else if (error.status === 404) {
        setErr('Voice is unavailable on this backend. Restart the API with the latest code.')
      } else if (error.status === 413) {
        setErr('That recording is too large. Please try a shorter recording.')
      } else if (error.status === 415) {
        setErr('This recording format is not supported by the voice service.')
      } else if (error.status === 502) {
        setErr("I couldn't hear that, try again or type.")
      } else if (error.status === 400 || error.status === 422) {
        setErr("I couldn't hear that, try again or type.")
      } else {
        setErr(apiErrorMessage(error))
      }
    } finally { setBusy(false); setActivePrompt('') }
  }

  const startRecording = async prompt => {
    if (!api.hasServiceCredentials()) {
      setErr('Enter the configured SERVICE_API_KEY in API credentials before using voice.')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setErr('Microphone recording is not supported in this browser.')
      return
    }
    setErr('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const preferredTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
      const mimeType = preferredTypes.find(type => MediaRecorder.isTypeSupported(type))
      if (!mimeType) {
        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        setErr('This browser cannot record a Sarvam-supported audio format. Try a current version of Chrome or Edge.')
        return
      }
      const recorder = new MediaRecorder(stream, { mimeType })
      recorderRef.current = recorder
      chunksRef.current = []
      recorder.ondataavailable = event => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        recorderRef.current = null
        setRecording(false)
        setRecordingSeconds(0)
        if (!blob.size) {
          setErr('No audio was captured. Please try again.')
          return
        }
        const selectedMerchant = prompt?.merchant || merchant
        const selectedSession = selectedMerchant === merchant ? session : null
        void sendVoice(blob, selectedMerchant, selectedSession)
      }
      recorder.start()
      setActivePrompt(prompt?.text || '')
      setRecordingSeconds(0)
      setRecording(true)
    } catch (error) {
      streamRef.current?.getTracks().forEach(track => track.stop())
      streamRef.current = null
      if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
        setErr('Microphone permission was denied. Allow microphone access in your browser and try again.')
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        setErr('No microphone was found. Connect a microphone and try again.')
      } else {
        setErr('The microphone could not be started. Check that it is connected and try again.')
      }
    }
  }

  const playReply = async audio => {
    try {
      const player = new Audio(`data:${audio.content_type};base64,${audio.data_base64}`)
      await player.play()
    } catch {
      setErr('Your browser could not play the reply. Try the replay button again.')
    }
  }

  const send = async msg => {
    if (!msg.trim() || busy || recording) return
    if (!api.hasServiceCredentials()) {
      setErr('Enter the configured SERVICE_API_KEY in API credentials. The browser cannot read the backend .env; it only sends a key entered here.')
      return
    }
    setBusy(true); setErr('')
    setLog(l => [...l, { me: true, text: msg }])
    try {
      const r = await api.chat(merchant, msg, session)
      setSession(r.session_id)
      setLog(l => [...l, { text: r.reply, actions: r.actions, meta: `${r.language} · ${r.intent} · planner: ${r.planner}` }])
      setText('')
    } catch (e) {
      if (e.status === 401) {
        onServiceAuthFailure()
        setErr('The merchant API key saved in this tab was rejected. It has been cleared; enter the exact current SERVICE_API_KEY and try again.')
      } else {
        setErr(apiErrorMessage(e))
      }
    } finally { setBusy(false) }
  }

  return (
    <section>
      <div className="row">
        <select value={merchant} disabled={busy || recording} onChange={e => pick(e.target.value)}>
          {MERCHANTS.map(([id, label]) => <option key={id} value={id}>{id} — {label}</option>)}
        </select>
      </div>
      <section className="voice-hero" aria-label="Voice message">
        <div className="voice-copy">
          <span className="eyebrow">VOICE · PUSH TO TALK</span>
          <h2>Talk to your teammate</h2>
          <p className="muted">Tap the mic, speak naturally, then tap again to send.</p>
        </div>
        <button
          className={recording ? 'mic-hero recording' : 'mic-hero'}
          aria-label={recording ? 'Stop voice recording' : 'Start voice recording'}
          aria-pressed={recording}
          title={voiceEnabled ? 'Record a voice message (up to 30 seconds)' : 'Set VOICE_BACKEND=sarvam and SARVAM_API_KEY in .env'}
          disabled={busy || (!voiceEnabled && !recording)}
          onClick={recording ? stopRecording : () => startRecording()}
        >
          <span className={recording ? 'mic-icon stop-icon' : 'mic-icon'} aria-hidden="true">
            {recording ? '■' : <svg viewBox="0 0 24 24" focusable="false"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" /><path d="M19 11a7 7 0 0 1-14 0M12 18v4m-4 0h8" /></svg>}
          </span>
          <span>{recording ? 'Stop recording' : 'Start talking'}</span>
        </button>
        <p className="voice-status" aria-live="polite">
          {recording
            ? <><span className="listening-pulse" aria-hidden="true" /> Listening… {String(Math.floor(recordingSeconds / 60)).padStart(2, '0')}:{String(recordingSeconds % 60).padStart(2, '0')} / 00:30</>
            : busy ? 'Transcribing and preparing a reply…' : voiceStatusError || (voiceEnabled ? 'Ready when you are' : 'Voice is turned off')}
        </p>
        {recording && activePrompt && <p className="say-prompt">Say: “{activePrompt}”</p>}
        <div className="voice-prompts" aria-label="One-click voice demo prompts">
          {VOICE_PROMPTS.map(prompt => (
            <button
              key={prompt.label}
              className="ghost voice-prompt"
              disabled={!voiceEnabled || busy || recording}
              onClick={() => {
                if (prompt.merchant !== merchant) pick(prompt.merchant)
                void startRecording(prompt)
              }}
            >{prompt.label}</button>
          ))}
        </div>
      </section>
      {err && <p className="error" role="alert">{err}</p>}
      <div className="chat">
        {log.length === 0 && <p className="muted">Pick a sample or type a message (Hindi, Hinglish, Telugu, Kannada or English).</p>}
        {log.map((m, i) => (
          <div key={i} className={m.me ? 'bubble me' : 'bubble bot'}>
            <div>{m.text}</div>
            {m.detectedLanguage && <span className="language-badge">Detected · {LANGUAGE_NAMES[m.detectedLanguage] || m.detectedLanguage}</span>}
            {m.actions?.length > 0 && (
              <div className="action-panel">
                <strong>What the teammate did</strong>
                {m.actions.map((a, j) => (
                  <div key={j} className="action">
                    <code>{a.tool}</code>
                    <span className="tier-rail" aria-label={a.tier ? `Tier ${a.tier}` : 'No tier'}>
                      {[1, 2, 3].map(tier => <span key={tier} className={a.tier === tier ? `tier-step active tier-${tier}` : 'tier-step'} />)}
                    </span>
                    <span className="muted">Tier {a.tier ?? '–'}</span> <Chip status={a.status} />
                  </div>
                ))}
              </div>
            )}
            {m.audio && <button className="ghost compact audio-replay" onClick={() => playReply(m.audio)}>Play / replay reply</button>}
            {m.meta && <div className="muted small">{m.meta}</div>}
          </div>
        ))}
      </div>
      <div className="row">
        <input className="grow" value={text} placeholder="Merchant message…" disabled={busy || recording}
          onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send(text)} />
        <button onClick={() => send(text)} disabled={busy || recording}>{busy ? '…' : 'Send'}</button>
      </div>
      <div className="row wrap">{SAMPLES.map(s => <button key={s} className="ghost" onClick={() => send(s)}>{s}</button>)}</div>
    </section>
  )
}

function Operator({ api, operatorVerified }) {
  const [data, setData] = useState({ approvals: [], escalations: [], audit: [] })
  const [chain, setChain] = useState(null)
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')

  const refresh = useCallback(async () => {
    if (!api.hasOperatorCredentials()) {
      setData({ approvals: [], escalations: [], audit: [] })
      setErr('Set OPERATOR_API_KEYS in the project root .env, then enter a configured operator ID and matching key above to load the console.')
      return
    }
    try {
      const [approvals, escalations, audit] = await Promise.all([api.approvals(), api.escalations(), api.audit()])
      setData({ approvals, escalations, audit: [...audit].reverse() }); setErr('')
    } catch (e) { setErr(apiErrorMessage(e)) }
  }, [api])
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t) }, [refresh])

  const act = async fn => {
    try { const r = await fn(); if (r?.outcome) setNote(`${r.outcome.tool}: ${r.outcome.status}`); await refresh() }
    catch (e) { setErr(apiErrorMessage(e)) }
  }

  return (
    <section>
      {!operatorVerified && api.hasOperatorCredentials() && <p className="muted small">Credentials are present. Select <b>Verify operator</b> above to confirm them.</p>}
      {err && <p className="error">{err}</p>}
      {note && <p className="ok">Last action → {note}</p>}
      <h3>Tier 2 · Awaiting approval ({data.approvals.length})</h3>
      {data.approvals.length === 0 && <p className="muted">Nothing pending.</p>}
      {data.approvals.map(t => (
        <div key={t.id} className="card">
          <b>{t.tool_name}</b> <span className="muted">for {t.merchant_id} · risk {t.risk_score} · proposed by {t.proposed_by}</span>
          <pre>{JSON.stringify(t.params, null, 2)}</pre>
          <div className="row">
            <button onClick={() => act(() => api.decide(t.id, 'approve'))}>Approve &amp; execute</button>
            <button className="ghost" onClick={() => act(() => api.decide(t.id, 'reject'))}>Reject</button>
          </div>
        </div>
      ))}
      <h3>Tier 3 · Escalations ({data.escalations.length})</h3>
      {data.escalations.length === 0 && <p className="muted">No open escalations.</p>}
      {data.escalations.map(t => (
        <div key={t.id} className="card">
          <b>{t.tool_name}</b> <span className="muted">for {t.merchant_id} · risk {t.risk_score}</span>
          <p className="small">Why: {t.brief?.why_escalated?.join(', ')}</p>
          <details><summary>Case brief</summary><pre>{JSON.stringify(t.brief, null, 2)}</pre></details>
          <button className="ghost" onClick={() => act(() => api.closeEscalation(t.id))}>Mark resolved</button>
        </div>
      ))}
      <h3>Audit trail</h3>
      <div className="row">
        <button className="ghost" onClick={async () => setChain(await api.verifyAudit().catch(e => ({ error: apiErrorMessage(e) })))}>Verify hash chain</button>
        {chain && (chain.error ? <span className="error">{chain.error}</span>
          : <span className={chain.valid ? 'ok' : 'error'}>{chain.valid ? `Intact · ${chain.events_checked} events` : `Tampered at #${chain.first_invalid_seq}`}</span>)}
      </div>
      <div className="scroll">
        <table>
          <thead><tr><th>#</th><th>Event</th><th>Actor</th><th>Tool</th><th>Decision</th><th>Tier</th></tr></thead>
          <tbody>{data.audit.map(e => (
            <tr key={e.seq}><td>{e.seq}</td><td>{e.event_type}</td><td>{e.actor}</td><td>{e.tool_name || '–'}</td><td>{e.decision || '–'}</td><td>{e.tier ?? '–'}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}

export default function App() {
  const [creds, setCreds] = useState(load)
  const [tab, setTab] = useState('chat')
  const [health, setHealth] = useState(null)
  const [operatorVerified, setOperatorVerified] = useState('')
  const [voiceStatus, setVoiceStatus] = useState(null)
  const [voiceStatusError, setVoiceStatusError] = useState('')
  const api = useMemo(() => makeApi(creds), [creds])
  const clearRejectedServiceKey = useCallback(() => {
    // A service-key failure must not also discard independently verified operator credentials.
    setCreds(current => ({ ...current, serviceKey: '' }))
  }, [])
  useEffect(() => { sessionStorage.setItem('creds', JSON.stringify(creds)); setOperatorVerified('') }, [creds])
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ status: 'down' })) }, [api])
  useEffect(() => {
    let active = true
    setVoiceStatus(null)
    setVoiceStatusError('')
    api.voiceStatus().then(status => {
      if (active) setVoiceStatus(status)
    }).catch(error => {
      if (!active) return
      if (error.status === 401 && api.hasServiceCredentials()) {
        clearRejectedServiceKey()
        setVoiceStatusError('The merchant API key was rejected. Enter the current SERVICE_API_KEY.')
      } else if (error.status === 401) {
        setVoiceStatusError('Enter the configured SERVICE_API_KEY to check voice availability.')
      } else if (error.status === 404) {
        setVoiceStatusError('Voice status is unavailable on this backend. Restart the API with the latest code.')
      } else {
        setVoiceStatusError(BACKEND_UNREACHABLE_MESSAGE)
      }
    })
    return () => { active = false }
  }, [api, clearRejectedServiceKey])
  const verifyOperator = async () => {
    try { const identity = await api.whoami(); setOperatorVerified(identity.operator_id) }
    catch (e) { setOperatorVerified(''); window.alert(apiErrorMessage(e)) }
  }

  return (
    <main>
      <header>
        <h1>Merchant AI Teammate</h1>
        <span className="banner">SIMULATED Paytm-style tools · no production APIs connected</span>
        <span className={health?.status === 'ok' ? 'ok small' : 'error small'}>API: {health?.status ?? '…'}</span>
      </header>
      <Credentials creds={creds} setCreds={setCreds} operatorVerified={operatorVerified} onVerify={verifyOperator}
        serviceKeyConfigured={health?.configuration?.service_api_key_configured} />
      <nav>
        <button className={tab === 'chat' ? 'tab on' : 'tab'} onClick={() => setTab('chat')}>Merchant chat</button>
        <button className={tab === 'ops' ? 'tab on' : 'tab'} onClick={() => setTab('ops')}>Operator console</button>
      </nav>
      {tab === 'chat' ? <Chat
        api={api}
        onServiceAuthFailure={clearRejectedServiceKey}
        voiceEnabled={voiceStatus?.enabled === true}
        voiceStatusError={voiceStatusError}
      /> : <Operator api={api} operatorVerified={operatorVerified} />}
    </main>
  )
}
