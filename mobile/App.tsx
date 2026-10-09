/**
 * Baykuş Optik — prototype of the in-app scan feature.
 *
 * Scan with the phone's own document scanner (VisionKit on iOS, ML Kit on Android, through
 * react-native-document-scanner-plugin), send the JPEG to the reading server (app/server.py), then show
 * either "scan again" or the result: questions to confirm, answers, and the marked photo.
 * The server's JSON is the same one the web page (app/static/index.html) uses.
 */
import { useState } from 'react';
import {
  ActivityIndicator, Image, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import DocumentScanner, { ResponseType, ScanDocumentResponseStatus } from 'react-native-document-scanner-plugin';

const DEFAULT_SERVER = 'http://192.168.1.185:8000';
const SUBJECTS: Record<string, string> = { turkce: 'Türkçe', sosyal: 'Sosyal', matematik: 'Matematik', fen: 'Fen' };
const OPTIONS = ['A', 'B', 'C', 'D', 'E'];

type Question = { question: number; answer: string | null; status: string; weak: boolean };
type Confirm = { subject: string; question: number; reason: 'weak' | 'multiple'; suggested: string | null; image: string };
type Result = {
  run: string;
  seconds: number;
  retake?: string[];
  issues?: string[];
  answers: Record<string, Question[]>;
  summary: Record<string, { marked: number; ambiguous: number; blank: number }>;
  confirm: Confirm[];
  overlay: string;
};
type Phase = 'idle' | 'loading' | 'retake' | 'result' | 'error';

const key = (s: string, q: number) => `${s}-${q}`;

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <Main />
    </SafeAreaProvider>
  );
}

function Main() {
  const [server, setServer] = useState(DEFAULT_SERVER);
  const [phase, setPhase] = useState<Phase>('idle');
  const [message, setMessage] = useState('');
  const [retake, setRetake] = useState<string[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [tab, setTab] = useState('turkce');
  const [saved, setSaved] = useState(false);
  const [zoom, setZoom] = useState(false);

  async function scan() {
    let jpegBase64: string;
    try {
      const { scannedImages, status } = await DocumentScanner.scanDocument({
        croppedImageQuality: 92, maxNumDocuments: 1, responseType: ResponseType.Base64,
      });
      if (status === ScanDocumentResponseStatus.Cancel || !scannedImages?.length) return;
      jpegBase64 = scannedImages[0];
    } catch (err) {
      setMessage(`Tarayıcı açılamadı: ${String(err)}`);
      return setPhase('error');
    }
    setPhase('loading');
    setMessage('Form okunuyor…');
    try {
      // Sent as base64 text (a string body is the most reliable upload in React Native); the server decodes it.
      const res = await withTimeout(fetch(`${server}/api/process`, {
        method: 'POST', body: jpegBase64,
        headers: { 'Content-Type': 'text/plain', 'X-Encoding': 'base64', 'X-Filename': 'tarama.jpg' },
      }), 90_000);
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || `HTTP ${res.status}`);
      if (r.retake?.length) {
        setRetake(r.retake);
        return setPhase('retake');
      }
      setResult(r); setChoices({}); setSaved(false); setTab('turkce');
      setPhase('result');
    } catch (err) {
      const text = String(err);
      setMessage(text.includes('Network request failed') || text.includes('zaman aşımı')
        ? `Sunucuya bağlanılamadı (${server}). Bilgisayarda sunucu --http ile açık mı, telefon aynı Wi-Fi'de mi?`
        : text);
      setPhase('error');
    }
  }

  async function save() {
    if (!result) return;
    try {
      const res = await fetch(`${server}/api/confirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run: result.run, choices }),
      });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || `HTTP ${res.status}`);
      setSaved(true);
    } catch (err) {
      setMessage(`Kaydedilemedi: ${String(err)}`);
    }
  }

  const pending = result ? result.confirm.filter((c) => !(key(c.subject, c.question) in choices)).length : 0;

  return (
    <SafeAreaView style={s.screen} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={s.content}>
        <View style={s.header}>
          <View style={s.logo}><Text style={s.logoText}>B</Text></View>
          <View>
            <Text style={s.h1}>Baykuş Optik</Text>
            <Text style={s.sub}>Optik formunu tara, cevaplarını gör.</Text>
          </View>
        </View>

        {phase === 'idle' && (
          <View style={s.card}>
            <Button title="Formu tara" onPress={scan} />
            <Text style={[s.note, { marginTop: 12 }]}>
              Formu düz bir masaya koy, dört köşesi görünsün, gölge düşmesin. Tarayıcı kağıdı kendisi bulup kırpar.
            </Text>
            <Text style={[s.label, { marginTop: 16 }]}>Sunucu adresi</Text>
            <TextInput style={s.input} value={server} onChangeText={setServer} autoCapitalize="none"
                       autoCorrect={false} keyboardType="url" />
            <Text style={s.note}>Bilgisayarda: .venv/bin/python -B app/server.py --http</Text>
          </View>
        )}

        {phase === 'loading' && (
          <View style={[s.card, s.row]}>
            <ActivityIndicator />
            <Text style={{ marginLeft: 12 }}>{message}</Text>
          </View>
        )}

        {phase === 'retake' && (
          <View style={[s.card, s.bad]}>
            <Status ok={false} title="Formu tekrar tara" sub="Bu taramadan cevaplar güvenilir şekilde okunamadı." />
            {retake.map((r) => <Text key={r} style={s.bullet}>• {r}</Text>)}
            <Button title="Tekrar tara" onPress={scan} />
          </View>
        )}

        {phase === 'error' && (
          <View style={[s.card, s.bad]}>
            <Status ok={false} title="Bir sorun oldu" sub={message} />
            <Button title="Tekrar dene" secondary onPress={() => setPhase('idle')} />
          </View>
        )}

        {phase === 'result' && result && (
          <>
            <View style={s.card}>
              <Status ok title="Form okundu" sub={`${Object.values(result.answers).flat().length} soru okundu · ${result.seconds} sn`} />
              <View style={s.chips}>
                {Object.entries(result.summary).map(([k, v]) => (
                  <View key={k} style={s.chip}>
                    <Text style={s.chipNum}>{v.marked + v.ambiguous}</Text>
                    <Text style={s.chipText}>{SUBJECTS[k]}</Text>
                    <Text style={s.chipText}>{v.blank} boş</Text>
                  </View>
                ))}
              </View>
              {(result.issues || []).map((x) => (
                <View key={x} style={s.issue}><Text><Text style={s.issueB}>Dikkat: </Text>{x}</Text></View>
              ))}
            </View>

            {result.confirm.length > 0 && (
              <View style={s.card}>
                <Text style={s.h2}>Emin olamadığımız sorular</Text>
                <Text style={s.sub}>Fotoğraftaki işareti kontrol edip hangi şıkkı işaretlediğini seç.</Text>
                {result.confirm.map((c) => {
                  const k = key(c.subject, c.question);
                  const sel = choices[k];
                  return (
                    <View key={k} style={[s.qCard, sel ? s.qDone : null]}>
                      <View style={s.qHead}>
                        <Text style={s.qTitle}>{SUBJECTS[c.subject]} · Soru {c.question}</Text>
                        <Text style={[s.qState, sel ? { color: C.ok } : null]}>
                          {sel ? `✓ ${sel === '-' ? 'Boş' : sel}` : 'Seçim bekliyor'}
                        </Text>
                      </View>
                      <Text style={s.qText}>
                        {c.reason === 'multiple'
                          ? `Birden fazla şık (${(c.suggested || '').split('').join(' ve ')}) işaretli görünüyor. Hangisini işaretlemek istedin?`
                          : 'İşaret çok açık ya da yarım görünüyor. Hangi şıkkı işaretledin?'}
                      </Text>
                      <Image source={{ uri: c.image }} style={s.crop} resizeMode="contain" />
                      <View style={s.opts}>
                        {[...OPTIONS, '-'].map((o) => (
                          <Pressable key={o} onPress={() => { setChoices({ ...choices, [k]: o }); setSaved(false); }}
                                     style={[s.opt, sel === o ? s.optSel : null,
                                             !sel && (c.suggested || '').includes(o) ? s.optHint : null]}>
                            <Text style={[s.optText, sel === o ? { color: '#fff' } : null, o === '-' ? { fontSize: 14 } : null]}>
                              {o === '-' ? 'Boş' : o}
                            </Text>
                          </Pressable>
                        ))}
                      </View>
                    </View>
                  );
                })}
              </View>
            )}

            <View style={s.card}>
              <Text style={s.h2}>Cevapların</Text>
              <View style={s.tabs}>
                {Object.keys(result.answers).map((k) => (
                  <Pressable key={k} onPress={() => setTab(k)} style={[s.tab, tab === k ? s.tabOn : null]}>
                    <Text style={[s.tabText, tab === k ? { color: C.ink } : null]}>{SUBJECTS[k]}</Text>
                  </Pressable>
                ))}
              </View>
              <Answers rows={result.answers[tab]} subject={tab} confirm={result.confirm} choices={choices} />
            </View>

            <View style={s.card}>
              <Text style={s.h2}>İşaretli fotoğraf</Text>
              <Text style={s.sub}>Okumanın doğru olduğunu gözle kontrol et. Büyütmek için dokun.</Text>
              <Pressable onPress={() => setZoom(true)}>
                <Overlay uri={result.overlay} />
              </Pressable>
              <Text style={s.note}>Kırmızı: işaretli · Turuncu: belirsiz · Yeşil: boş. Yeşil halkalar balonların üstünde
                durmuyorsa okuma hatalıdır, formu tekrar tara.</Text>
            </View>
          </>
        )}
      </ScrollView>

      {phase === 'result' && result && (
        <SafeAreaView edges={['bottom']} style={s.bar}>
          {pending > 0 && <Text style={[s.note, { textAlign: 'center', marginBottom: 8 }]}>{pending} soru için seçim bekleniyor</Text>}
          <View style={s.row}>
            <Button title="Yeni form" secondary compact onPress={scan} />
            <View style={{ width: 8 }} />
            <View style={{ flex: 1 }}>
              <Button title={saved ? 'Kaydedildi ✓' : 'Cevapları kaydet'} disabled={pending > 0 || saved} onPress={save} />
            </View>
          </View>
        </SafeAreaView>
      )}

      <Modal visible={zoom} animationType="fade" onRequestClose={() => setZoom(false)}>
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          <ScrollView maximumZoomScale={5} minimumZoomScale={1} centerContent contentContainerStyle={{ flexGrow: 1, justifyContent: 'center' }}>
            {result && <Overlay uri={result.overlay} />}
          </ScrollView>
          <SafeAreaView edges={['top']} style={{ position: 'absolute', right: 12, top: 0 }}>
            <Pressable onPress={() => setZoom(false)} style={s.close}><Text style={{ fontSize: 22 }}>×</Text></Pressable>
          </SafeAreaView>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function Answers({ rows, subject, confirm, choices }:
  { rows: Question[]; subject: string; confirm: Confirm[]; choices: Record<string, string> }) {
  const asked = new Set(confirm.map((c) => key(c.subject, c.question)));
  return (
    <View style={s.grid}>
      {rows.map((q) => {
        const k = key(subject, q.question);
        let value = q.answer || '—';
        let style = q.answer ? null : s.aBlank;
        if (q.status === 'invisible') { value = '?'; style = s.aInv; }
        if (asked.has(k)) {
          if (k in choices) { value = choices[k] === '-' ? '—' : choices[k]; style = s.aConfirmed; }
          else { value = '?'; style = s.aPending; }
        }
        return (
          <View key={k} style={[s.a, style]}>
            <Text style={s.aText}><Text style={s.aNum}>{q.question}) </Text>{value}</Text>
          </View>
        );
      })}
    </View>
  );
}

function Overlay({ uri }: { uri: string }) {
  const [ratio, setRatio] = useState(0.5);
  return (
    <Image source={{ uri }} style={[s.photo, { aspectRatio: ratio }]} resizeMode="contain"
           onLoad={(e) => { const { width, height } = e.nativeEvent.source; if (width && height) setRatio(width / height); }} />
  );
}

function Status({ ok, title, sub }: { ok: boolean; title: string; sub: string }) {
  return (
    <View style={[s.row, { alignItems: 'flex-start', marginBottom: 8 }]}>
      <View style={[s.icon, { backgroundColor: ok ? C.okSoft : C.badSoft }]}>
        <Text style={{ color: ok ? C.ok : C.bad, fontWeight: '800' }}>{ok ? '✓' : '!'}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={s.h2}>{title}</Text>
        <Text style={s.sub}>{sub}</Text>
      </View>
    </View>
  );
}

function Button({ title, onPress, secondary, disabled, compact }:
  { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean; compact?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={disabled}
               style={({ pressed }) => [s.btn, secondary ? s.btnSecondary : s.btnPrimary, compact ? { paddingHorizontal: 16 } : null,
                                        disabled ? { opacity: 0.45 } : null, pressed ? { opacity: 0.8 } : null]}>
      <Text style={[s.btnText, { color: secondary ? C.accent : '#fff' }]}>{title}</Text>
    </Pressable>
  );
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return Promise.race([p, new Promise<T>((_, reject) => setTimeout(() => reject(new Error('zaman aşımı')), ms))]);
}

const C = {
  bg: '#f5f6f8', card: '#ffffff', ink: '#14202c', muted: '#5f6b78', line: '#e4e7ec',
  accent: '#1a6fb0', accentSoft: '#e6f0f8', ok: '#1f7a4d', okSoft: '#e5f4ec',
  warn: '#8a5300', warnSoft: '#fff3df', warnLine: '#f2cf95', bad: '#b3261e', badSoft: '#fdecea', badLine: '#f1b8b3',
};

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 140 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  logo: { width: 40, height: 40, borderRadius: 12, backgroundColor: C.accent, alignItems: 'center', justifyContent: 'center' },
  logoText: { color: '#fff', fontWeight: '800', fontSize: 20 },
  h1: { fontSize: 20, fontWeight: '700', color: C.ink },
  h2: { fontSize: 17, fontWeight: '700', color: C.ink, marginBottom: 2 },
  sub: { fontSize: 14, color: C.muted },
  note: { fontSize: 13, color: C.muted, marginTop: 8 },
  label: { fontSize: 13, fontWeight: '600', color: C.muted, marginBottom: 6 },
  input: { borderWidth: 1, borderColor: C.line, borderRadius: 10, padding: 10, fontSize: 15, color: C.ink },
  card: { backgroundColor: C.card, borderRadius: 16, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: C.line },
  bad: { borderColor: C.badLine },
  row: { flexDirection: 'row', alignItems: 'center' },
  icon: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  bullet: { fontSize: 15, color: C.ink, marginVertical: 6 },
  btn: { minHeight: 50, borderRadius: 14, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12, marginTop: 4 },
  btnPrimary: { backgroundColor: C.accent },
  btnSecondary: { backgroundColor: C.accentSoft },
  btnText: { fontSize: 16, fontWeight: '700' },
  chips: { flexDirection: 'row', gap: 8, marginTop: 8 },
  chip: { flex: 1, backgroundColor: C.bg, borderRadius: 12, paddingVertical: 8, alignItems: 'center' },
  chipNum: { fontSize: 18, fontWeight: '700', color: C.ink },
  chipText: { fontSize: 12, color: C.muted },
  issue: { backgroundColor: C.warnSoft, borderColor: C.warnLine, borderWidth: 1, borderRadius: 12, padding: 10, marginTop: 10 },
  issueB: { color: C.warn, fontWeight: '700' },
  qCard: { borderWidth: 1, borderColor: C.warnLine, borderRadius: 14, padding: 12, marginTop: 12 },
  qDone: { borderColor: C.line },
  qHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  qTitle: { fontSize: 16, fontWeight: '700', color: C.ink },
  qState: { fontSize: 13, fontWeight: '600', color: C.warn },
  qText: { fontSize: 14, color: C.muted, marginVertical: 6 },
  crop: { width: '100%', aspectRatio: 4.5, borderRadius: 10, backgroundColor: '#fff' },
  opts: { flexDirection: 'row', gap: 6, marginTop: 10 },
  opt: { flex: 1, minHeight: 46, borderRadius: 12, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center',
         borderWidth: 2, borderColor: 'transparent' },
  optSel: { backgroundColor: C.accent },
  optHint: { borderColor: C.accent },
  optText: { fontSize: 17, fontWeight: '700', color: C.ink },
  tabs: { flexDirection: 'row', backgroundColor: C.bg, borderRadius: 12, padding: 4, marginVertical: 12 },
  tab: { flex: 1, minHeight: 38, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  tabOn: { backgroundColor: C.card },
  tabText: { fontSize: 13, fontWeight: '600', color: C.muted },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  a: { width: '23.5%', backgroundColor: C.bg, borderRadius: 10, paddingVertical: 7, alignItems: 'center' },
  aText: { fontSize: 15, fontWeight: '700', color: C.ink },
  aNum: { fontSize: 13, fontWeight: '400', color: C.muted },
  aBlank: {},
  aPending: { backgroundColor: C.warnSoft, borderWidth: 1, borderColor: C.warnLine },
  aConfirmed: { backgroundColor: C.okSoft },
  aInv: { backgroundColor: C.badSoft },
  photo: { width: '100%', marginTop: 10, borderRadius: 10, backgroundColor: '#fff' },
  bar: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: 'rgba(245,246,248,0.97)',
         borderTopWidth: 1, borderTopColor: C.line },
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.9)', alignItems: 'center', justifyContent: 'center' },
});
