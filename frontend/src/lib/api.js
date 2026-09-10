import axios from "axios";
import { API_URL } from "../config";

// =========================
// CLIENT AXIOS
// =========================
export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

// =========================
// FUNZIONI DI UTILITÀ
// =========================

// Formatta importi in euro
export function fmtEur(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value ?? 0);
}

// Formatta date ISO → dd/mm/yyyy
export function fmtDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("it-IT").format(new Date(value));
}

// Ritorna la data di oggi in formato YYYY-MM-DD
export function todayIso() {
  return new Date().toISOString().slice(0, 10);
}
