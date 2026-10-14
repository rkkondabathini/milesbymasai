// Shared by the browser app and the Node build. Phone + email -> lookup id + AES key (PBKDF2).
const MilesAuth = (() => {
  const te = new TextEncoder();
  const b64 = (u8) => btoa(String.fromCharCode(...u8));
  const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  const hex = (u8) => [...u8].map((x) => x.toString(16).padStart(2, "0")).join("");
  const normPhone = (p) => String(p || "").replace(/\D/g, "").slice(-10);
  const normEmail = (e) => String(e || "").trim().toLowerCase();

  async function derive(phone, email, salt, iter) {
    const base = await crypto.subtle.importKey("raw", te.encode(normPhone(phone) + "|" + normEmail(email)),
      "PBKDF2", false, ["deriveBits"]);
    const bits = await crypto.subtle.deriveBits(
      { name: "PBKDF2", hash: "SHA-256", salt: unb64(salt), iterations: iter }, base, 384);
    const u = new Uint8Array(bits);
    return { id: hex(u.slice(0, 16)), key: u.slice(16, 48) };
  }
  const aes = (key, use) => crypto.subtle.importKey("raw", key, "AES-GCM", false, [use]);

  async function encrypt(key, obj) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await aes(key, "encrypt"),
      te.encode(JSON.stringify(obj)));
    return { iv: b64(iv), ct: b64(new Uint8Array(ct)) };
  }
  async function decrypt(key, rec) {
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(rec.iv) }, await aes(key, "decrypt"),
      unb64(rec.ct));
    return JSON.parse(new TextDecoder().decode(pt));
  }
  return { derive, encrypt, decrypt, b64, normPhone, normEmail };
})();
