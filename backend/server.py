"""Wolf's Mind ASD - Gestionale backend (FastAPI + MongoDB)."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import Response as RawResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from models import (UserCreate, UserLogin, UserUpdate, TesseratoCreate, TesseratoUpdate,
                     TipoPacchettoCreate, TipoPacchettoUpdate, AbbonamentoCreate,
                     LezioneCreate, RicevutaCreate, RicevutaUpdate, MovimentoCreate,
                     MovimentoUpdate, OrganizzazioneUpdate, SendReceiptEmail, now_iso)
from auth_utils import (hash_password, verify_password, create_access_token,
                         create_refresh_token, set_auth_cookies, clear_auth_cookies,
                         get_current_user_from_db, require_admin)
from pdf_utils import generate_receipt_pdf, generate_balance_report_pdf
from email_utils import send_email_with_attachment

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Wolf's Mind Gestionale")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def current_user(request: Request):
    return await get_current_user_from_db(request, db)


def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="ID non valido")


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    doc.pop("password_hash", None)
    return doc


# ============================================================
# AUTH
# ============================================================
@api.post("/auth/login")
async def login(payload: UserLogin, request: Request, response: Response):
    email = payload.email.lower()
    ident = email  # key on email only (behind ingress client IP is not stable)
    now = datetime.now(timezone.utc)
    attempt = await db.login_attempts.find_one({"_id": ident})
    if attempt and attempt.get("count", 0) >= 5 and attempt.get("locked_until"):
        try:
            if datetime.fromisoformat(attempt["locked_until"]) > now:
                raise HTTPException(status_code=429,
                                     detail="Troppi tentativi. Riprova tra 15 minuti.")
        except (ValueError, TypeError):
            pass
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        new_count = (attempt.get("count", 0) if attempt else 0) + 1
        upd = {"count": new_count, "updated_at": now.isoformat()}
        if new_count >= 5:
            upd["locked_until"] = (now + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"_id": ident}, {"$set": upd}, upsert=True)
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if user.get("active") is False:
        raise HTTPException(status_code=403, detail="Utente disattivato")
    await db.login_attempts.delete_one({"_id": ident})
    uid = str(user["_id"])
    a = create_access_token(uid, email, user["role"])
    r = create_refresh_token(uid)
    set_auth_cookies(response, a, r)
    return {"user": serialize(user), "access_token": a}


@api.post("/auth/logout")
async def logout(response: Response, user=Depends(current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return user


# ============================================================
# USERS
# ============================================================
@api.get("/users")
async def list_users(user=Depends(current_user)):
    # Both admin and tecnico can read the list (needed for Movimenti select),
    # but only admin sees password/full data - password_hash is stripped anyway.
    docs = await db.users.find({}, {"password_hash": 0}).to_list(500)
    return [serialize(d) for d in docs]


@api.post("/users")
async def create_user(payload: UserCreate, user=Depends(current_user)):
    require_admin(user)
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email già registrata")
    doc = {"email": email, "password_hash": hash_password(payload.password),
           "name": payload.name, "role": payload.role,
           "percentuale_compenso": float(payload.percentuale_compenso or 0),
           "active": True, "created_at": now_iso()}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.patch("/users/{uid}")
async def update_user(uid: str, payload: UserUpdate, user=Depends(current_user)):
    require_admin(user)
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "password" in upd:
        upd["password_hash"] = hash_password(upd.pop("password"))
    if not upd:
        raise HTTPException(status_code=400, detail="Nessun dato da aggiornare")
    res = await db.users.update_one({"_id": oid(uid)}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    doc = await db.users.find_one({"_id": oid(uid)}, {"password_hash": 0})
    return serialize(doc)


@api.delete("/users/{uid}")
async def delete_user(uid: str, user=Depends(current_user)):
    require_admin(user)
    if uid == user["id"]:
        raise HTTPException(status_code=400, detail="Non puoi eliminare te stesso")
    res = await db.users.delete_one({"_id": oid(uid)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"ok": True}


# ============================================================
# TESSERATI
# ============================================================
@api.get("/tesserati")
async def list_tesserati(user=Depends(current_user)):
    q = {}
    if user["role"] != "admin":
        q["created_by"] = user["id"]
    docs = await db.tesserati.find(q).sort("cognome", 1).to_list(2000)
    return [serialize(d) for d in docs]


@api.post("/tesserati")
async def create_tesserato(payload: TesseratoCreate, user=Depends(current_user)):
    doc = payload.model_dump()
    doc["created_at"] = now_iso()
    doc["created_by"] = user["id"]
    res = await db.tesserati.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.get("/tesserati/{tid}")
async def get_tesserato(tid: str, user=Depends(current_user)):
    doc = await db.tesserati.find_one({"_id": oid(tid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Tesserato non trovato")
    return serialize(doc)


@api.patch("/tesserati/{tid}")
async def update_tesserato(tid: str, payload: TesseratoUpdate, user=Depends(current_user)):
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not upd:
        raise HTTPException(status_code=400, detail="Nessun dato da aggiornare")
    res = await db.tesserati.update_one({"_id": oid(tid)}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tesserato non trovato")
    doc = await db.tesserati.find_one({"_id": oid(tid)})
    return serialize(doc)


@api.delete("/tesserati/{tid}")
async def delete_tesserato(tid: str, user=Depends(current_user)):
    require_admin(user)
    res = await db.tesserati.delete_one({"_id": oid(tid)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tesserato non trovato")
    return {"ok": True}


# ============================================================
# TIPI PACCHETTO
# ============================================================
@api.get("/tipi-pacchetto")
async def list_tipi(user=Depends(current_user)):
    docs = await db.tipi_pacchetto.find({}).sort("nome", 1).to_list(200)
    return [serialize(d) for d in docs]


@api.post("/tipi-pacchetto")
async def create_tipo(payload: TipoPacchettoCreate, user=Depends(current_user)):
    require_admin(user)
    doc = payload.model_dump(); doc["created_at"] = now_iso()
    res = await db.tipi_pacchetto.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.patch("/tipi-pacchetto/{pid}")
async def update_tipo(pid: str, payload: TipoPacchettoUpdate, user=Depends(current_user)):
    require_admin(user)
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    res = await db.tipi_pacchetto.update_one({"_id": oid(pid)}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pacchetto non trovato")
    doc = await db.tipi_pacchetto.find_one({"_id": oid(pid)})
    return serialize(doc)


@api.delete("/tipi-pacchetto/{pid}")
async def delete_tipo(pid: str, user=Depends(current_user)):
    require_admin(user)
    res = await db.tipi_pacchetto.delete_one({"_id": oid(pid)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pacchetto non trovato")
    return {"ok": True}


# ============================================================
# ABBONAMENTI
# ============================================================
async def _count_lezioni_for_abbonamento(abbonamento_id: str) -> int:
    """Count lessons where this abbonamento appears in any participant."""
    return await db.lezioni.count_documents({"partecipanti.abbonamento_id": abbonamento_id})


async def _spesa_totale_per_tesserato(tesserato_id: str) -> float:
    rics = await db.ricevute.find({"tesserato_id": tesserato_id,
                                     "annullata": {"$ne": True}}).to_list(2000)
    return sum(r.get("totale", 0) for r in rics)


@api.get("/abbonamenti")
async def list_abbonamenti(tesserato_id: Optional[str] = None, user=Depends(current_user)):
    q = {}
    if tesserato_id:
        q["tesserato_id"] = tesserato_id
    if user["role"] != "admin":
        # tecnico vede solo abbonamenti dei suoi tesserati (o creati da lui)
        my_tess = await db.tesserati.find({"created_by": user["id"]}, {"_id": 1}).to_list(2000)
        my_ids = [str(t["_id"]) for t in my_tess]
        or_q = [{"tesserato_id": {"$in": my_ids}}, {"created_by": user["id"]}]
        q["$or"] = or_q
    docs = await db.abbonamenti.find(q).sort("data_acquisto", -1).to_list(1000)
    result = []
    for d in docs:
        s = serialize(d)
        used = await _count_lezioni_for_abbonamento(s["id"])
        s["lezioni_effettuate"] = used
        if s.get("num_lezioni_totali"):
            s["lezioni_residue"] = max(0, s["num_lezioni_totali"] - used)
        else:
            s["lezioni_residue"] = None
        result.append(s)
    return result


@api.post("/abbonamenti")
async def create_abbonamento(payload: AbbonamentoCreate, user=Depends(current_user)):
    doc = payload.model_dump(); doc["created_at"] = now_iso()
    doc["created_by"] = user["id"]
    res = await db.abbonamenti.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.delete("/abbonamenti/{aid}")
async def delete_abbonamento(aid: str, user=Depends(current_user)):
    require_admin(user)
    res = await db.abbonamenti.delete_one({"_id": oid(aid)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Abbonamento non trovato")
    return {"ok": True}


@api.get("/abbonamenti/{aid}/storico")
async def storico_abbonamento(aid: str, user=Depends(current_user)):
    ab = await db.abbonamenti.find_one({"_id": oid(aid)})
    if not ab:
        raise HTTPException(status_code=404, detail="Abbonamento non trovato")
    lezioni = await db.lezioni.find({"partecipanti.abbonamento_id": aid}).sort("data", -1).to_list(1000)
    # Ricevute che citano questo abbonamento tra gli item
    rics = await db.ricevute.find({"items.abbonamento_id": aid, "annullata": {"$ne": True}}).to_list(500)
    speso = 0.0
    for r in rics:
        for it in r.get("items", []):
            if it.get("abbonamento_id") == aid:
                speso += float(it.get("importo", 0))
    tess = await db.tesserati.find_one({"_id": oid(ab["tesserato_id"])}) if ab.get("tesserato_id") else None
    return {
        "abbonamento": serialize(ab),
        "tesserato": serialize(tess) if tess else None,
        "lezioni": [serialize(l) for l in lezioni],
        "ricevute": [serialize(r) for r in rics],
        "spesa_totale_abbonamento": speso,
    }


# ============================================================
# LEZIONI (collettive con partecipanti multipli)
# ============================================================
@api.get("/lezioni")
async def list_lezioni(abbonamento_id: Optional[str] = None, tecnico_id: Optional[str] = None,
                       user=Depends(current_user)):
    q = {}
    if abbonamento_id:
        q["partecipanti.abbonamento_id"] = abbonamento_id
    if tecnico_id:
        q["tecnico_id"] = tecnico_id
    if user["role"] != "admin" and not tecnico_id:
        q["tecnico_id"] = user["id"]
    docs = await db.lezioni.find(q).sort("data", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api.post("/lezioni")
async def create_lezione(payload: LezioneCreate, user=Depends(current_user)):
    if not payload.partecipanti:
        raise HTTPException(status_code=400, detail="Aggiungi almeno un partecipante")
    # Validate all abbonamenti exist and have residue
    for p in payload.partecipanti:
        ab = await db.abbonamenti.find_one({"_id": oid(p.abbonamento_id)})
        if not ab:
            raise HTTPException(status_code=404,
                                 detail=f"Abbonamento {p.abbonamento_id} non trovato")
        if ab.get("num_lezioni_totali"):
            used = await _count_lezioni_for_abbonamento(p.abbonamento_id)
            if used >= ab["num_lezioni_totali"]:
                tess = await db.tesserati.find_one({"_id": oid(ab["tesserato_id"])})
                nm = f"{tess.get('cognome','')} {tess.get('nome','')}" if tess else ""
                raise HTTPException(status_code=400,
                    detail=f"Abbonamento esaurito per {nm.strip()}")
    doc = payload.model_dump()
    doc["tecnico_id"] = payload.tecnico_id or user["id"]
    doc["created_by"] = user["id"]
    doc["created_at"] = now_iso()
    res = await db.lezioni.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.delete("/lezioni/{lid}")
async def delete_lezione(lid: str, user=Depends(current_user)):
    res = await db.lezioni.delete_one({"_id": oid(lid)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lezione non trovata")
    return {"ok": True}


# ============================================================
# RICEVUTE
# ============================================================
async def _next_receipt_number(year: int) -> tuple[str, int]:
    counter = await db.counters.find_one_and_update(
        {"_id": f"ricevute_{year}"}, {"$inc": {"seq": 1}},
        upsert=True, return_document=True)
    seq = counter["seq"]
    return f"{year}/{seq:05d}", seq


@api.get("/ricevute")
async def list_ricevute(user=Depends(current_user)):
    q = {}
    if user["role"] != "admin":
        q["emesso_per_id"] = user["id"]
    docs = await db.ricevute.find(q).sort("data", -1).to_list(2000)
    return [serialize(d) for d in docs]


@api.post("/ricevute")
async def create_ricevuta(payload: RicevutaCreate, user=Depends(current_user)):
    year = datetime.now(timezone.utc).year
    try:
        year = datetime.fromisoformat(payload.data.replace("Z", "+00:00")).year
    except Exception:
        pass
    tesserato = await db.tesserati.find_one({"_id": oid(payload.tesserato_id)})
    if not tesserato:
        raise HTTPException(status_code=404, detail="Tesserato non trovato")

    # Determine attribution: admin can attribute to another tecnico
    emesso_per_id = user["id"]
    emesso_per_nome = user["name"]
    if payload.emesso_per_id and user["role"] == "admin":
        target = await db.users.find_one({"_id": oid(payload.emesso_per_id)})
        if not target:
            raise HTTPException(status_code=404, detail="Tecnico non trovato")
        emesso_per_id = str(target["_id"])
        emesso_per_nome = target["name"]

    numero, seq = await _next_receipt_number(year)
    totale = sum(i.importo for i in payload.items)
    doc = {"numero": numero, "seq": seq, "anno": year, "data": payload.data,
           "tesserato_id": payload.tesserato_id,
           "tesserato_nome": f"{tesserato['cognome']} {tesserato['nome']}",
           "metodo_pagamento": payload.metodo_pagamento,
           "items": [i.model_dump() for i in payload.items],
           "totale": totale, "note": payload.note or "",
           "emesso_da_id": user["id"], "emesso_da_nome": user["name"],
           "emesso_per_id": emesso_per_id, "emesso_per_nome": emesso_per_nome,
           "annullata": False, "created_at": now_iso()}
    res = await db.ricevute.insert_one(doc)
    doc["_id"] = res.inserted_id
    rid = str(res.inserted_id)
    await db.movimenti.insert_one({
        "data": payload.data, "tipo": "entrata", "categoria": "Ricevuta",
        "descrizione": f"Ricevuta N.{numero} - {tesserato['cognome']} {tesserato['nome']}",
        "importo": totale, "tecnico_id": emesso_per_id, "ricevuta_id": rid,
        "created_at": now_iso(), "created_by": user["id"]})
    return serialize(doc)


@api.get("/ricevute/{rid}")
async def get_ricevuta(rid: str, user=Depends(current_user)):
    doc = await db.ricevute.find_one({"_id": oid(rid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Ricevuta non trovata")
    if user["role"] != "admin" and doc.get("emesso_per_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    return serialize(doc)


@api.patch("/ricevute/{rid}")
async def update_ricevuta(rid: str, payload: RicevutaUpdate, user=Depends(current_user)):
    require_admin(user)
    existing = await db.ricevute.find_one({"_id": oid(rid)})
    if not existing:
        raise HTTPException(status_code=404, detail="Ricevuta non trovata")
    upd = payload.model_dump(exclude_unset=True)
    if "items" in upd and upd["items"] is not None:
        upd["items"] = [i if isinstance(i, dict) else i.model_dump() for i in upd["items"]]
        upd["totale"] = sum(i["importo"] for i in upd["items"])
    if "emesso_per_id" in upd and upd["emesso_per_id"]:
        target = await db.users.find_one({"_id": oid(upd["emesso_per_id"])})
        if not target:
            raise HTTPException(status_code=404, detail="Tecnico non trovato")
        upd["emesso_per_nome"] = target["name"]
    await db.ricevute.update_one({"_id": oid(rid)}, {"$set": upd})
    # Sync linked movimento
    mv_upd = {}
    if "totale" in upd: mv_upd["importo"] = upd["totale"]
    if "data" in upd: mv_upd["data"] = upd["data"]
    if "emesso_per_id" in upd: mv_upd["tecnico_id"] = upd["emesso_per_id"]
    if mv_upd:
        await db.movimenti.update_many({"ricevuta_id": rid}, {"$set": mv_upd})
    doc = await db.ricevute.find_one({"_id": oid(rid)})
    return serialize(doc)


@api.delete("/ricevute/{rid}")
async def delete_ricevuta(rid: str, user=Depends(current_user)):
    """Physical delete: also decrement counter if this is the last receipt of the year."""
    require_admin(user)
    doc = await db.ricevute.find_one({"_id": oid(rid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Ricevuta non trovata")
    year = doc.get("anno")
    seq = doc.get("seq")
    counter = await db.counters.find_one({"_id": f"ricevute_{year}"})
    await db.ricevute.delete_one({"_id": oid(rid)})
    await db.movimenti.delete_many({"ricevuta_id": rid})
    # Decrement counter only if this was the last one issued
    if counter and seq is not None and counter.get("seq") == seq:
        new_seq = seq - 1
        if new_seq <= 0:
            await db.counters.delete_one({"_id": f"ricevute_{year}"})
        else:
            await db.counters.update_one({"_id": f"ricevute_{year}"}, {"$set": {"seq": new_seq}})
    return {"ok": True, "numero_riutilizzabile": bool(counter and counter.get("seq") == seq)}


async def _load_org() -> dict:
    org = await db.organizzazione.find_one({"_id": "config"})
    if not org:
        org = {"_id": "config", "name": "Wolf's Mind A.S.D.",
               "address": "Via Rivera, 17 - 10070 Front (TO)",
               "fiscal_code": "9205285010", "email": "wolfmind.asd@gmail.com",
               "pec": "wolfmind.asd@pec.it",
               "affiliation": "Affiliata Libertas - TO773",
               "president_name": "Drovelli Caivano Bruno",
               "logo_base64": None, "president_signature_base64": None}
        await db.organizzazione.insert_one(org)
    return org


@api.get("/ricevute/{rid}/pdf")
async def ricevuta_pdf(rid: str, user=Depends(current_user)):
    doc = await db.ricevute.find_one({"_id": oid(rid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Ricevuta non trovata")
    if user["role"] != "admin" and doc.get("emesso_per_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    tesserato = await db.tesserati.find_one({"_id": oid(doc["tesserato_id"])})
    org = await _load_org()
    pdf_bytes = generate_receipt_pdf(serialize(doc), serialize(tesserato) if tesserato else {},
                                     org, doc.get("emesso_per_nome") or doc.get("emesso_da_nome", ""))
    filename = f"Ricevuta_{doc['numero'].replace('/', '-')}.pdf"
    return RawResponse(pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{filename}"'})


@api.post("/ricevute/{rid}/send-email")
async def send_ricevuta_email(rid: str, payload: SendReceiptEmail, user=Depends(current_user)):
    doc = await db.ricevute.find_one({"_id": oid(rid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Ricevuta non trovata")
    if user["role"] != "admin" and doc.get("emesso_per_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    tesserato = await db.tesserati.find_one({"_id": oid(doc["tesserato_id"])})
    org = await _load_org()
    pdf_bytes = generate_receipt_pdf(serialize(doc), serialize(tesserato) if tesserato else {},
                                     org, doc.get("emesso_per_nome") or doc.get("emesso_da_nome", ""))
    filename = f"Ricevuta_{doc['numero'].replace('/', '-')}.pdf"
    org_name = org.get('name', "Wolf's Mind A.S.D.")
    subject = f"Ricevuta N.{doc['numero']} - {org_name}"
    tess_nome = tesserato.get('nome', '') if tesserato else ''
    html = f"""
    <table role="presentation" width="100%" style="font-family:Arial,sans-serif">
      <tr><td style="padding:24px">
        <p>Gentile {tess_nome},</p>
        <p>in allegato trovi la ricevuta <strong>N. {doc['numero']}</strong> emessa da
        {org_name}.</p>
        <p style="white-space:pre-line">{(payload.message or '').strip()}</p>
        <p style="font-size:12px;color:#888;margin-top:24px">
        Email inviata da {org_name}. Non rispondiamo a richieste
        di password o dati di pagamento via email.</p>
      </td></tr>
    </table>
    """
    email_id = await send_email_with_attachment(
        to=payload.email, subject=subject, html=html,
        attachment_bytes=pdf_bytes, attachment_filename=filename)
    await db.ricevute.update_one({"_id": oid(rid)},
                                  {"$set": {"last_sent_email": payload.email,
                                            "last_sent_at": now_iso()}})
    return {"ok": True, "email_id": email_id}


@api.get("/ricevute/{rid}/whatsapp-link")
async def whatsapp_link(rid: str, user=Depends(current_user)):
    doc = await db.ricevute.find_one({"_id": oid(rid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Ricevuta non trovata")
    tesserato = await db.tesserati.find_one({"_id": oid(doc["tesserato_id"])})
    org = await _load_org()
    tel = (tesserato.get("telefono", "") if tesserato else "").replace(" ", "").replace("+", "")
    org_name = org.get('name', "Wolf's Mind ASD")
    tess_nome = tesserato.get('nome', '') if tesserato else ''
    text = (f"Gentile {tess_nome}, in allegato la ricevuta "
            f"N.{doc['numero']} di {org_name}. Buona giornata!")
    if tel:
        return {"url": f"https://wa.me/{tel}?text={quote(text)}"}
    return {"url": f"https://wa.me/?text={quote(text)}"}


# ============================================================
# MOVIMENTI
# ============================================================
@api.get("/movimenti")
async def list_movimenti(date_from: Optional[str] = None, date_to: Optional[str] = None,
                          user=Depends(current_user)):
    q = {}
    if user["role"] != "admin":
        q["tecnico_id"] = user["id"]
    if date_from or date_to:
        q["data"] = {}
        if date_from: q["data"]["$gte"] = date_from
        if date_to: q["data"]["$lte"] = date_to + "T23:59:59"
    docs = await db.movimenti.find(q).sort("data", -1).to_list(3000)
    return [serialize(d) for d in docs]


@api.post("/movimenti")
async def create_movimento(payload: MovimentoCreate, user=Depends(current_user)):
    require_admin(user)
    doc = payload.model_dump(); doc["created_at"] = now_iso()
    doc["created_by"] = user["id"]
    res = await db.movimenti.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.patch("/movimenti/{mid}")
async def update_movimento(mid: str, payload: MovimentoUpdate, user=Depends(current_user)):
    require_admin(user)
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    res = await db.movimenti.update_one({"_id": oid(mid)}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Movimento non trovato")
    doc = await db.movimenti.find_one({"_id": oid(mid)})
    return serialize(doc)


@api.delete("/movimenti/{mid}")
async def delete_movimento(mid: str, user=Depends(current_user)):
    require_admin(user)
    res = await db.movimenti.delete_one({"_id": oid(mid)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Movimento non trovato")
    return {"ok": True}


@api.get("/movimenti/riepilogo-mensile")
async def riepilogo_mensile(year: int, user=Depends(current_user)):
    q = {"data": {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31T23:59:59"}}
    if user["role"] != "admin":
        q["tecnico_id"] = user["id"]
    movs = await db.movimenti.find(q).to_list(5000)
    by_month = {f"{year}-{m:02d}": {"entrate": 0, "uscite": 0, "count": 0}
                for m in range(1, 13)}
    for m in movs:
        ym = (m.get("data") or "")[:7]
        if ym in by_month:
            if m["tipo"] == "entrata":
                by_month[ym]["entrate"] += m["importo"]
            else:
                by_month[ym]["uscite"] += m["importo"]
            by_month[ym]["count"] += 1
    result = [{"mese": ym, **v, "saldo": v["entrate"] - v["uscite"]}
              for ym, v in sorted(by_month.items())]
    return {"year": year, "mesi": result,
            "totali": {
                "entrate": sum(v["entrate"] for v in by_month.values()),
                "uscite": sum(v["uscite"] for v in by_month.values()),
                "saldo": sum(v["entrate"] - v["uscite"] for v in by_month.values())}}


# ============================================================
# DASHBOARD & REPORT
# ============================================================
async def _tesserati_ids_for_user(user: dict) -> list[str]:
    if user["role"] == "admin":
        return []  # all
    tess = await db.tesserati.find({"created_by": user["id"]}, {"_id": 1}).to_list(3000)
    return [str(t["_id"]) for t in tess]


@api.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    now = datetime.now(timezone.utc)
    month_start = f"{now.year:04d}-{now.month:02d}-01"
    year_start = f"{now.year:04d}-01-01"

    if user["role"] == "admin":
        tesserati_count = await db.tesserati.count_documents({})
        abbon_count = await db.abbonamenti.count_documents({})
    else:
        tesserati_count = await db.tesserati.count_documents({"created_by": user["id"]})
        my_ids = await _tesserati_ids_for_user(user)
        abbon_count = await db.abbonamenti.count_documents({
            "$or": [{"tesserato_id": {"$in": my_ids}}, {"created_by": user["id"]}]})

    receipts_q = {"data": {"$gte": month_start}, "annullata": {"$ne": True}}
    if user["role"] != "admin":
        receipts_q["emesso_per_id"] = user["id"]
    receipts_month = await db.ricevute.find(receipts_q).to_list(1000)
    incassato_mese = sum(r.get("totale", 0) for r in receipts_month)

    mv_q = {"data": {"$gte": year_start}}
    if user["role"] != "admin":
        mv_q["tecnico_id"] = user["id"]
    movs = await db.movimenti.find(mv_q).to_list(5000)
    entrate = sum(m["importo"] for m in movs if m["tipo"] == "entrata")
    uscite = sum(m["importo"] for m in movs if m["tipo"] == "uscita")

    limit = (now + timedelta(days=30)).date().isoformat()
    today = now.date().isoformat()
    scad_q = {"$or": [
        {"scadenza_tesseramento": {"$lte": limit, "$gte": today}},
        {"scadenza_visita_medica": {"$lte": limit, "$gte": today}},
    ]}
    if user["role"] != "admin":
        scad_q = {"$and": [scad_q, {"created_by": user["id"]}]}
    scad = await db.tesserati.find(scad_q).to_list(500)

    # Compenso personale (tecnico)
    compenso_maturato = None
    if user["role"] == "tecnico":
        rics = await db.ricevute.find({"emesso_per_id": user["id"],
                                          "annullata": {"$ne": True},
                                          "data": {"$gte": year_start}}).to_list(2000)
        flusso = 0.0
        for r in rics:
            for it in r.get("items", []):
                if not it.get("esclude_da_compensi"):
                    flusso += float(it.get("importo", 0))
        perc = float(user.get("percentuale_compenso") or 0)
        compenso_maturato = flusso * perc / 100.0

    return {"tesserati_count": tesserati_count, "abbon_count": abbon_count,
            "ricevute_mese_count": len(receipts_month),
            "incassato_mese": incassato_mese,
            "entrate_anno": entrate, "uscite_anno": uscite,
            "saldo_anno": entrate - uscite,
            "compenso_maturato": compenso_maturato,
            "scadenze_imminenti": [serialize(t) for t in scad]}


@api.get("/report/bilancio")
async def report_bilancio(date_from: str, date_to: str, user=Depends(current_user)):
    q = {"data": {"$gte": date_from, "$lte": date_to + "T23:59:59"}}
    if user["role"] != "admin":
        q["tecnico_id"] = user["id"]
    movs = await db.movimenti.find(q).sort("data", 1).to_list(5000)
    entrate = sum(m["importo"] for m in movs if m["tipo"] == "entrata")
    uscite = sum(m["importo"] for m in movs if m["tipo"] == "uscita")
    return {"movimenti": [serialize(m) for m in movs],
            "totali": {"entrate": entrate, "uscite": uscite, "saldo": entrate - uscite}}


@api.get("/report/bilancio/pdf")
async def report_bilancio_pdf(date_from: str, date_to: str, user=Depends(current_user)):
    q = {"data": {"$gte": date_from, "$lte": date_to + "T23:59:59"}}
    if user["role"] != "admin":
        q["tecnico_id"] = user["id"]
    movs = await db.movimenti.find(q).sort("data", 1).to_list(5000)
    entrate = sum(m["importo"] for m in movs if m["tipo"] == "entrata")
    uscite = sum(m["importo"] for m in movs if m["tipo"] == "uscita")
    org = await _load_org()
    pdf_bytes = generate_balance_report_pdf(
        org, [serialize(m) for m in movs], date_from, date_to,
        {"entrate": entrate, "uscite": uscite, "saldo": entrate - uscite})
    return RawResponse(pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": 'inline; filename="Bilancio.pdf"'})


# ============================================================
# COMPENSI (con esclusione item)
# ============================================================
@api.get("/compensi")
async def compensi(date_from: Optional[str] = None, date_to: Optional[str] = None,
                   user=Depends(current_user)):
    year = datetime.now(timezone.utc).year
    date_from = date_from or f"{year}-01-01"
    date_to = date_to or f"{year}-12-31"
    users_q = {"role": "tecnico"}
    if user["role"] != "admin":
        users_q["_id"] = oid(user["id"])
    tecnici = await db.users.find(users_q).to_list(200)
    result = []
    for t in tecnici:
        tid = str(t["_id"])
        rics = await db.ricevute.find({
            "emesso_per_id": tid,
            "data": {"$gte": date_from, "$lte": date_to + "T23:59:59"},
            "annullata": {"$ne": True}}).to_list(2000)
        flusso_totale = sum(r.get("totale", 0) for r in rics)
        flusso_compensabile = 0.0
        for r in rics:
            for it in r.get("items", []):
                if not it.get("esclude_da_compensi"):
                    flusso_compensabile += float(it.get("importo", 0))
        perc = float(t.get("percentuale_compenso") or 0)
        compenso = flusso_compensabile * perc / 100.0
        result.append({"tecnico_id": tid, "tecnico_nome": t.get("name"),
                       "percentuale": perc, "n_ricevute": len(rics),
                       "flusso_generato": flusso_totale,
                       "flusso_compensabile": flusso_compensabile,
                       "compenso_dovuto": compenso})
    return {"compensi": result, "date_from": date_from, "date_to": date_to}


# ============================================================
# ORGANIZZAZIONE
# ============================================================
@api.get("/organizzazione")
async def get_org(user=Depends(current_user)):
    org = await _load_org()
    org["id"] = org.pop("_id", "config")
    return org


@api.patch("/organizzazione")
async def update_org(payload: OrganizzazioneUpdate, user=Depends(current_user)):
    require_admin(user)
    await _load_org()
    upd = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if upd:
        await db.organizzazione.update_one({"_id": "config"}, {"$set": upd})
    org = await db.organizzazione.find_one({"_id": "config"})
    org["id"] = org.pop("_id", "config")
    return org


# ============================================================
app.include_router(api)

app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@wolfsmind.it").lower()
    admin_pass = os.environ.get("ADMIN_PASSWORD", "Admin2026!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "email": admin_email, "password_hash": hash_password(admin_pass),
            "name": "Amministratore", "role": "admin",
            "percentuale_compenso": 0, "active": True, "created_at": now_iso()})
    elif not verify_password(admin_pass, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
                                   {"$set": {"password_hash": hash_password(admin_pass)}})
    await db.users.create_index("email", unique=True)
    await _load_org()
    # Backfill esclude_da_compensi on legacy tipi_pacchetto docs
    await db.tipi_pacchetto.update_many(
        {"esclude_da_compensi": {"$exists": False}},
        {"$set": {"esclude_da_compensi": False}})
    if await db.tipi_pacchetto.count_documents({}) == 0:
        await db.tipi_pacchetto.insert_many([
            {"nome": "12 lezioni", "descrizione": "Pacchetto 12 lezioni",
             "num_lezioni": 12, "prezzo_default": 100.0, "attivo": True,
             "esclude_da_compensi": False, "created_at": now_iso()},
            {"nome": "8 lezioni", "descrizione": "Pacchetto 8 lezioni",
             "num_lezioni": 8, "prezzo_default": 70.0, "attivo": True,
             "esclude_da_compensi": False, "created_at": now_iso()},
            {"nome": "Tesseramento annuale", "descrizione": "Quota associativa annuale",
             "num_lezioni": None, "prezzo_default": 30.0, "attivo": True,
             "esclude_da_compensi": True, "created_at": now_iso()}])


@app.on_event("shutdown")
async def shutdown():
    client.close()
