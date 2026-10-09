/**
 * CYCLONEX — Firebase App, Authentication & Analytics Core Module
 * Project: trata-f4b62
 * Primary Meteorological Identity Provider & Telemetry Engine
 */

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
import { getAnalytics, logEvent, isSupported } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-analytics.js";
import { 
  getAuth, 
  signInWithEmailAndPassword, 
  signOut as fbSignOut,
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";

// Web app's Firebase configuration
export const firebaseConfig = {
  apiKey: "AIzaSyAmdMi2cNo09nmMwbnQWObCxba638Z16Hk",
  authDomain: "trata-f4b62.firebaseapp.com",
  projectId: "trata-f4b62",
  storageBucket: "trata-f4b62.firebasestorage.app",
  messagingSenderId: "236232455522",
  appId: "1:236232455522:web:714abc4d18577e2612e83b",
  measurementId: "G-H6BQBVJ39K"
};

// Initialize Firebase App
export const app = initializeApp(firebaseConfig);

// Initialize Firebase Authentication
export const auth = getAuth(app);

// Domain mapping strategy for authorized meteorological identities
const OPERATOR_DOMAIN = "@cyclonex.internal";
const VALID_OPERATOR_PREFIXES = ["MET-", "IMD-", "RSMC-", "SIH-", "OPERATOR-", "ADMIN-"];

/**
 * Maps an official Employee / Operator ID to its canonical Firebase email identity.
 * Validates format to prevent arbitrary input conversion.
 * 
 * @param {string} employeeId - e.g. "MET-26070"
 * @returns {string} - e.g. "met-26070@cyclonex.internal"
 * @throws {Error} - if the Employee ID format is invalid
 */
export function mapEmployeeIdToEmail(employeeId) {
  if (!employeeId || typeof employeeId !== "string") {
    throw new Error("Invalid Employee ID: value must be a non-empty string.");
  }

  const clean = employeeId.trim();

  // If already an authorized internal or corporate email
  if (clean.includes("@")) {
    const parts = clean.toLowerCase().split("@");
    const localPart = parts[0];
    const hasValidPrefix = VALID_OPERATOR_PREFIXES.some(prefix => 
      localPart.toUpperCase().startsWith(prefix.toLowerCase())
    );
    if (!hasValidPrefix && !clean.endsWith(OPERATOR_DOMAIN)) {
      throw new Error("Unauthorized identity domain or unrecognized operator credential.");
    }
    return clean.toLowerCase();
  }

  const upper = clean.toUpperCase();
  const isValid = VALID_OPERATOR_PREFIXES.some(prefix => upper.startsWith(prefix));
  if (!isValid) {
    throw new Error(
      "Unrecognized Employee ID prefix. Authorized designations: " + 
      VALID_OPERATOR_PREFIXES.join(", ")
    );
  }

  // Sanitize local part for standard email formatting
  const sanitizedLocal = clean.toLowerCase().replace(/[^a-z0-9_-]/g, "");
  return sanitizedLocal + OPERATOR_DOMAIN;
}

/**
 * Authenticates an operator directly against Firebase Authentication.
 * Primary identity provider method for CYCLONEX workstation.
 *
 * @param {string} employeeId - Official Operator / Employee ID
 * @param {string} password - Security Access Key
 * @returns {Promise<{user: Object, idToken: string, employeeId: string}>}
 */
export async function signInOperator(employeeId, password) {
  if (!employeeId || !password) {
    throw new Error("Both Employee ID and Security Access Key are required.");
  }

  const mappedEmail = mapEmployeeIdToEmail(employeeId);
  const cleanId = employeeId.trim().toUpperCase();

  // Call Firebase Client SDK Authentication
  const userCredential = await signInWithEmailAndPassword(auth, mappedEmail, password);
  const user = userCredential.user;

  // Retrieve genuine cryptographic Firebase ID token
  const idToken = await user.getIdToken();

  return {
    user,
    idToken,
    employeeId: cleanId,
    email: user.email
  };
}

/**
 * Signs out the operator from Firebase Authentication and terminates the client session.
 * 
 * @returns {Promise<void>}
 */
export async function signOutOperator() {
  try {
    await fbSignOut(auth);
  } catch (err) {
    console.warn("[CYCLONEX] Firebase signOut warning:", err);
  }
}

// Initialize Analytics conditionally (safely handles environments/browsers where IndexedDB or cookies are restricted)
export let analytics = null;

isSupported().then(supported => {
  if (supported) {
    try {
      analytics = getAnalytics(app);
      console.log("[CYCLONEX] Firebase App & Analytics initialized (Project: " + firebaseConfig.projectId + ")");
      const pageName = window.location.pathname.split("/").pop() || "index.html";
      logEvent(analytics, "page_view", {
        page_title: document.title,
        page_path: window.location.pathname,
        page_location: window.location.href,
        cyclonex_module: pageName
      });
    } catch (err) {
      console.warn("[CYCLONEX] Firebase Analytics initialization notice:", err);
    }
  } else {
    console.log("[CYCLONEX] Firebase App connected; Analytics not supported in current environment.");
  }
}).catch(err => {
  console.warn("[CYCLONEX] Firebase Analytics support check notice:", err);
});

/**
 * Sanitized telemetry event logger for CYCLONEX operational events.
 * Strictly filters out credentials, tokens, passwords, and sensitive keys.
 */
export function trackEvent(eventName, eventParams = {}) {
  if (!analytics) return;

  // Enforce data hygiene: strip any sensitive fields
  const safeParams = {};
  const blockedKeys = ["password", "token", "idtoken", "refreshtoken", "key", "secret", "access_token"];

  for (const [k, v] of Object.entries(eventParams)) {
    if (!blockedKeys.includes(k.toLowerCase()) && typeof v !== "object") {
      safeParams[k] = v;
    }
  }

  try {
    logEvent(analytics, eventName, {
      timestamp: new Date().toISOString(),
      ...safeParams
    });
  } catch (e) {
    // Non-blocking telemetry
  }
}

// Attach to window for global availability across CYCLONEX scripts
window.CYCLONEX_FIREBASE = {
  app,
  auth,
  signInOperator,
  signOutOperator,
  mapEmployeeIdToEmail,
  getAnalytics: () => analytics,
  trackEvent,
  config: firebaseConfig,
  onAuthStateChanged: (cb) => onAuthStateChanged(auth, cb)
};
