// Passkey login and registration (WebAuthn) for the admin pages.
// Buttons: data-passkey="login" or data-passkey="register" (with
// data-token for an invite). The server (unodb/auth.py) creates the
// options and verifies the result; this only talks to the browser.
"use strict";

(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (!meta || !window.PublicKeyCredential) {
    document.querySelectorAll("[data-passkey]").forEach((button) => {
      button.disabled = true;
      showError(button, "This browser doesn't support passkeys.");
    });
    return;
  }

  // --- base64url <-> ArrayBuffer (for browsers without the JSON helpers)
  function toBuffer(text) {
    const base64 = text.replace(/-/g, "+").replace(/_/g, "/");
    const binary = atob(base64 + "===".slice((base64.length + 3) % 4));
    return Uint8Array.from(binary, (c) => c.charCodeAt(0)).buffer;
  }

  function toText(buffer) {
    const binary = String.fromCharCode(...new Uint8Array(buffer));
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function creationOptions(json) {
    if (PublicKeyCredential.parseCreationOptionsFromJSON) {
      return PublicKeyCredential.parseCreationOptionsFromJSON(json);
    }
    return Object.assign({}, json, {
      challenge: toBuffer(json.challenge),
      user: Object.assign({}, json.user, { id: toBuffer(json.user.id) }),
      excludeCredentials: (json.excludeCredentials || []).map((c) =>
        Object.assign({}, c, { id: toBuffer(c.id) }),
      ),
    });
  }

  function requestOptions(json) {
    if (PublicKeyCredential.parseRequestOptionsFromJSON) {
      return PublicKeyCredential.parseRequestOptionsFromJSON(json);
    }
    return Object.assign({}, json, {
      challenge: toBuffer(json.challenge),
      allowCredentials: (json.allowCredentials || []).map((c) =>
        Object.assign({}, c, { id: toBuffer(c.id) }),
      ),
    });
  }

  function credentialJSON(credential) {
    if (credential.toJSON) return credential.toJSON();
    const r = credential.response;
    const response = { clientDataJSON: toText(r.clientDataJSON) };
    if (r.attestationObject) {
      response.attestationObject = toText(r.attestationObject);
      response.transports = r.getTransports ? r.getTransports() : [];
    } else {
      response.authenticatorData = toText(r.authenticatorData);
      response.signature = toText(r.signature);
      if (r.userHandle) response.userHandle = toText(r.userHandle);
    }
    return {
      id: credential.id,
      rawId: toText(credential.rawId),
      type: credential.type,
      response,
      clientExtensionResults: credential.getClientExtensionResults(),
      authenticatorAttachment: credential.authenticatorAttachment,
    };
  }

  // --- talking to the server
  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": meta.content,
      },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Error ${response.status}`);
    return data;
  }

  function showError(button, message) {
    const box = button.parentElement.querySelector("[data-passkey-error]");
    if (box) {
      box.textContent = message;
      box.hidden = false;
    }
  }

  async function register(button) {
    const nameInput = button.parentElement.querySelector("[data-passkey-name]");
    const options = await post("/admin/register/options", {
      token: button.dataset.token || "",
      name: nameInput ? nameInput.value : "",
    });
    const credential = await navigator.credentials.create({
      publicKey: creationOptions(options),
    });
    return post("/admin/register/verify", credentialJSON(credential));
  }

  async function login() {
    const options = await post("/admin/login/options", {});
    const credential = await navigator.credentials.get({
      publicKey: requestOptions(options),
    });
    return post("/admin/login/verify", credentialJSON(credential));
  }

  document.querySelectorAll("[data-passkey]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.setAttribute("aria-busy", "true");
      try {
        const result =
          button.dataset.passkey === "login" ? await login() : await register(button);
        window.location.href = result.next;
      } catch (error) {
        const messages = {
          NotAllowedError: "Cancelled or timed out. Please try again.",
          InvalidStateError: "This device already has a passkey for you.",
        };
        const message = messages[error.name] || error.message;
        showError(button, message);
      } finally {
        button.removeAttribute("aria-busy");
      }
    });
  });
})();
