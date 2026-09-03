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
    percentuale_compenso: float = 0.0


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
    numero_tessera: Optional[str] = None
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
    numero_tessera: Optional[str] = None
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


# --- Tipo Pacchetto ---
class TipoPacchettoBase(BaseModel):
    nome: str
    descrizione: str = ""
    num_lezioni: Optional[int] = None
    prezzo_default: float = 0.0
    attivo: bool = True
    esclude_da_compensi: bool = False


class TipoPacchettoCreate(TipoPacchettoBase):
    pass


class TipoPacchettoUpdate(BaseModel):
    nome: Optional[str] = None
    descrizione: Optional[str] = None
    num_lezioni: Optional[int] = None
    prezzo_default: Optional[float] = None
    attivo: Optional[bool] = None
    esclude_da_compensi: Optional[bool] = None


# --- Abbonamento ---
class AbbonamentoCreate(BaseModel):
    tesserato_id: str
    tipo_pacchetto_id: Optional[str] = None
    descrizione: str
    num_lezioni_totali: Optional[int] = None
    prezzo: float
    data_acquisto: str


# --- Lezione (collettiva) ---
class LezionePartecipante(BaseModel):
    tesserato_id: str
    abbonamento_id: str


class LezioneCreate(BaseModel):
    data: str
    luogo: str = ""
    tecnico_id: Optional[str] = None
    note: Optional[str] = ""
    partecipanti: List[LezionePartecipante] = Field(default_factory=list)


# --- Ricevuta ---
class RicevutaItem(BaseModel):
    descrizione: str
    num_lezioni: Optional[int] = None
    importo: float
    abbonamento_id: Optional[str] = None
    tipo_pacchetto_id: Optional[str] = None
    esclude_da_compensi: bool = False


class RicevutaCreate(BaseModel):
    tesserato_id: str
    data: str
    metodo_pagamento: str = "Contanti"
    items: List[RicevutaItem]
    note: Optional[str] = ""
    emesso_per_id: Optional[str] = None  # admin: attribute to a specific tecnico


class RicevutaUpdate(BaseModel):
    data: Optional[str] = None
    metodo_pagamento: Optional[str] = None
    items: Optional[List[RicevutaItem]] = None
    note: Optional[str] = None
    annullata: Optional[bool] = None
    emesso_per_id: Optional[str] = None


# --- Movimento ---
class MovimentoCreate(BaseModel):
    data: str
    tipo: Literal["entrata", "uscita"]
    categoria: str
    descrizione: str
    importo: float
    tecnico_id: Optional[str] = None
    ricevuta_id: Optional[str] = None


class MovimentoUpdate(BaseModel):
    data: Optional[str] = None
    tipo: Optional[Literal["entrata", "uscita"]] = None
    categoria: Optional[str] = None
    descrizione: Optional[str] = None
    importo: Optional[float] = None
    tecnico_id: Optional[str] = None


# --- Organizzazione ---
class OrganizzazioneUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    fiscal_code: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None
    affiliation: Optional[str] = None
    president_name: Optional[str] = None
    logo_base64: Optional[str] = None
    president_signature_base64: Optional[str] = None


class SendReceiptEmail(BaseModel):
    email: EmailStr
    message: Optional[str] = None


# --- Calendario Lezioni ---
class SlotCreate(BaseModel):
    data: str  # YYYY-MM-DD
    ora: str  # HH:MM
    durata_min: int = 60
    luogo: str = ""
    tecnico_id: Optional[str] = None
    capacita: int = 8
    descrizione: str = ""
    ricorrenza_settimanale: bool = False
    ricorrenza_fino_al: Optional[str] = None  # YYYY-MM-DD


class SlotUpdate(BaseModel):
    data: Optional[str] = None
    ora: Optional[str] = None
    durata_min: Optional[int] = None
    luogo: Optional[str] = None
    tecnico_id: Optional[str] = None
    capacita: Optional[int] = None
    descrizione: Optional[str] = None


class PrenotazioneCreate(BaseModel):
    slot_id: str
    tesserato_id: str
    abbonamento_id: Optional[str] = None


# --- Erogazione Compensi ---
class ErogaCompenso(BaseModel):
    tecnico_id: str
    data: str
    importo: float
    periodo_da: Optional[str] = None
    periodo_a: Optional[str] = None
    metodo: str = "Bonifico"
    note: Optional[str] = ""
