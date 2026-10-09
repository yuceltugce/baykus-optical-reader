# Baykuş Optik — telefon uygulaması (deneme)

Mevcut uygulamaya eklenecek "optik formu tara" özelliğinin denemesi. Telefonun kendi belge tarayıcısını açar
(iPhone: Apple VisionKit, Android: Google ML Kit — `react-native-document-scanner-plugin`), taranan formu
bilgisayardaki okuma sunucusuna (`app/server.py`) gönderir ve sonucu gösterir:

- **Tekrar tara** — yeni bir taramanın düzelteceği sorunlarda (kesik, ters, bükük, gölge); sonuç gösterilmez.
- **Sonuç** — emin olunamayan sorular (fotoğraf parçası + A–E / Boş), ders ders "1) A" cevaplar, işaretli
  fotoğraf; **Cevapları kaydet** → sunucuda `confirmed.json`.

Sunucunun JSON'u web sayfasıyla (`app/static/index.html`) aynıdır. Kod: `App.tsx` (tek ekran).

## iPhone'da çalıştırma

Bir kez:

1. App Store'dan **Xcode**'u kur, bir kez aç (lisansı kabul et, ek bileşenleri kur), sonra terminalde:
   `sudo xcode-select -s /Applications/Xcode.app`
2. Xcode → Settings → Accounts → **Apple hesabını** ekle (ücretsiz hesap yeter).
3. iPhone'u kabloyla bağla; iPhone'da **Ayarlar → Gizlilik ve Güvenlik → Geliştirici Modu**'nu aç.

Her seferinde, proje kökünden iki terminal:

```sh
.venv/bin/python -B app/server.py --http        # okuma sunucusu (uygulama http ile bağlanır)
cd mobile && npx expo run:ios --device          # derler, iPhone'a kurar, açar
```

İlk derlemede Xcode imzalama (Signing) için ekibini sormazsa ve hata verirse: `mobile/ios/BaykuOptik.xcworkspace`'i
Xcode'da aç → BaykuOptik hedefi → Signing & Capabilities → Team: kendi Apple hesabın.
iPhone ilk açılışta "güvenilmeyen geliştirici" derse: **Ayarlar → Genel → VPN ve Aygıt Yönetimi** → hesabına güven.
Ücretsiz hesapla kurulan uygulama 7 gün çalışır; sonra komutu tekrar çalıştır.

Uygulamada **Sunucu adresi** alanına sunucunun yazdığı adresi gir (ör. `http://192.168.1.185:8000`).
Telefon ve bilgisayar aynı Wi-Fi'de olmalı; ilk bağlantıda iPhone "yerel ağ" izni sorar.

## Notlar

- Tarayıcı simülatörde çalışmaz (`VNDocumentCameraViewController` yalnız gerçek cihazda); gerçek iPhone gerekir.
- `ios/` ve `android/` klasörleri `npx expo prebuild` ile üretilir, git'e girmez.
- Eklenti filtre seçtirmiyor: iPhone tarayıcısı varsayılan "Renkli" filtreyle döner (okuma kodu bu çıktıyla
  ölçüldü); Android'de ML Kit tam mod (`SCANNER_MODE_FULL`) eklentinin içinde sabit.
- Gerçek uygulamaya taşırken: sunucu adresi ayarı yerine sabit API adresi, HTTPS + kimlik doğrulama.
