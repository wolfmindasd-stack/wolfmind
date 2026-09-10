// frontend/src/lib/api.js
import axios from "axios";
import { API_URL } from "../config";

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

// Formattazioni di utilità (mantieni quelle che avevi)
export function fmtEur(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value ?? 0);
}

export function fmtDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("it-IT").format(new Date(value));
}
