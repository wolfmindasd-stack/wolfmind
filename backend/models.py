"""Pydantic models for the Wolf's Mind gestionale."""
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Users ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: Literal["admin", "tecnico"] = "tecnico"
    percentuale_compenso: float = 0.0  # % of receipts flow


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Literal["admin", "tecnico"]] = None
    percentuale_compenso: Optional[float] = None
    active: Optional[bool] = None
    password: Optional[str] = None


# --- Tesserato ---
class TesseratoBase(BaseModel):
    cognome: str
    nome: str
    codice_fiscale: str
    indirizzo: str = ""
    civico: str = ""
    cap: str = ""
    citta: str = ""
    provincia: str = ""
    email: Optional[str] = None
    telefono: Optional[str] = None
    data_nascita: Optional[str] = None
    scadenza_tesseramento: Optional[str] = None
    scadenza_visita_medica: Optional[str] = None
    note: Optional[str] = None


class TesseratoCreate(TesseratoBase):
    pass


class TesseratoUpdate(BaseModel):
    cognome: Optional[str] = None
    nome: Optional[str] = None
    codice_fiscale: Optional[str] = None
    indirizzo: Optional[str] = None
    civico: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    data_nascita: Optional[str] = None
    scadenza_tesseramento: Optional[str] = None
    scadenza_visita_medica: Optional[str] = None
    note: Optional[str] = None


# --- Tipo Pacchetto (subscription types - editable list) ---
class TipoPacchettoBase(BaseModel):
    nome: str  # e.g. "12 lezioni"
    descrizione: str = ""
    num_lezioni: Optional[int] = None  # null for "varie"
    prezzo_default: float = 0.0
    attivo: bool = True


class TipoPacchettoCreate(TipoPacchettoBase):
    pass


class TipoPacchettoUpdate(BaseModel):
    nome: Optional[str] = None
    descrizione: Optional[str] = None
    num_lezioni: Optional[int] = None
    prezzo_default: Optional[float] = None
    attivo: Optional[bool] = None


# --- Abbonamento (purchased subscription bound to a tesserato) ---
class AbbonamentoCreate(BaseModel):
    tesserato_id: str
    tipo_pacchetto_id: Optional[str] = None
    descrizione: str
    num_lezioni_totali: Optional[int] = None
    prezzo: float
    data_acquisto: str  # ISO date


# --- Lezione effettuata ---
class LezioneCreate(BaseModel):
    abbonamento_id: str
    data: str
    note: Optional[str] = ""


# --- Ricevuta ---
class RicevutaItem(BaseModel):
    descrizione: str
    num_lezioni: Optional[int] = None
    importo: float
    abbonamento_id: Optional[str] = None  # if this item is a subscription purchase


class RicevutaCreate(BaseModel):
    tesserato_id: str
    data: str
    metodo_pagamento: str = "Contanti"
    items: List[RicevutaItem]
    note: Optional[str] = ""


class RicevutaUpdate(BaseModel):
    data: Optional[str] = None
    metodo_pagamento: Optional[str] = None
    items: Optional[List[RicevutaItem]] = None
    note: Optional[str] = None
    annullata: Optional[bool] = None


# --- Movimento contabile ---
class MovimentoCreate(BaseModel):
    data: str
    tipo: Literal["entrata", "uscita"]
    categoria: str
    descrizione: str
    importo: float
    tecnico_id: Optional[str] = None  # for compensi/tech-linked entries
    ricevuta_id: Optional[str] = None  # auto-linked


class MovimentoUpdate(BaseModel):
    data: Optional[str] = None
    tipo: Optional[Literal["entrata", "uscita"]] = None
    categoria: Optional[str] = None
    descrizione: Optional[str] = None
    importo: Optional[float] = None
    tecnico_id: Optional[str] = None


# --- Organizzazione (single doc) ---
class OrganizzazioneUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    fiscal_code: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None
    affiliation: Optional[str] = None
    president_name: Optional[str] = None
    logo_base64: Optional[str] = None
    email_template: Optional[str] = None


# --- Send receipt ---
class SendReceiptEmail(BaseModel):
    email: EmailStr
    message: Optional[str] = None
