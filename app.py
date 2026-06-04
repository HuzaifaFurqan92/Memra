import os
import threading
import json
from typing import List, Dict
import uvicorn
from fastapi import Body, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from groq import Groq
import instructor
from auth import hash_password, verify_password, create_access_token, get_current_user
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime
# Bind your database layer
from database import init_db, get_db_context, UserModel, MessageModel

load_dotenv()  

app = FastAPI(title="Memra - Core Behavioral Memory Engine")

# Trigger table generation on startup
init_db()

# Engine clients setup
raw_groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", "").strip())
instructor_client = instructor.from_groq(raw_groq_client, mode=instructor.Mode.JSON)

# --- STRUCTURAL DATA SCHEMAS (Pydantic Models) ---
class ChatMessage(BaseModel):
    user_id: str     
    session_id: str  
    role: str        
    content: str

class ChatRequestPayload(BaseModel):
    content: str

class PendingCommitment(BaseModel):
    friction_trigger: str = Field(description="The specific action or context that caused psychological friction.")
    observed_cognitive_state: str = Field(description="The emotional or behavioral reaction observed (e.g., analysis paralysis).")
    mitigation_instruction: str = Field(description="The exact tactical prescription to bypass this friction block.")
    detected_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class PsychologicalConstraint(BaseModel):
    friction_trigger: str = Field(description="What specific event or planning style causes the user to freeze.")
    observed_cognitive_state: str = Field(description="The mental hurdle state triggered.")
    mitigation_instruction: str = Field(description="Directive for how future prompts must frame tasks.")
    times_observed: int = Field(default=1, description="Count of trait occurrences.",exclude=True)
    confidence: float = Field(default=0.3, description="Confidence metric.",exclude=True)
    last_seen: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    # 🛠️ FORCE LIVE SYSTEM TIMESTAMP
    @field_validator("last_seen", mode="before")
    @classmethod
    def force_live_time(cls, v):
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    def reinforce_metric(self):   # proper method
        self.times_observed += 1
        self.confidence = min(1.0, round(self.confidence + 0.15, 2))
        self.last_seen = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
class ExecutionStyle(BaseModel):
    preferred_pacing: str = Field(description="Natural work rhythms.")
    communication_preference: str = Field(description="Tone style.")
    vulnerabilities: List[str] = Field(description="Observed pattern traps.")
        
class UserBehaviorProfile(BaseModel):
    primary_goals: List[str] = Field(description="Continuous core objectives.")
    psychological_constraints: List[PsychologicalConstraint] = Field(description="Identified hurdles.")
    execution_style: ExecutionStyle = Field(description="Rhythms analysis.")
    pending_commitments: List[PendingCommitment] = Field(default=[], description="F03: Isolation queue for unverified traits.") # <-- ADD THIS LINE

def reinforce_metric(self):
        """Linearly scales confidence with frequency up to a max cap of 1.0."""
        self.times_observed += 1
        # Increase confidence by 0.15 for every recurring observation, capped at 1.0
        self.confidence = min(1.0, round(self.confidence + 0.15, 2))
        self.last_seen = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
# --- FEATURE 2 OUTPUT SCHEMA ---
class ProactiveCheckInResponse(BaseModel):
    opening_hook: str = Field(description="A highly specific, zero-fluff contextual question.")
    rational_target: str = Field(description="Internal engineering reasoning.")

@app.post("/auth/register")
async def register(user_id:str,password:str):
    with get_db_context() as db:
        existing = db.query(UserModel).filter(UserModel.user_id==user_id).first()
        if existing: 
            raise HTTPException(status_code=400, detail="User ID already exists.")
        new_user = UserModel(
            user_id = user_id,
            hashed_password = hash_password(password),
            profile_json= "{}"
        )
        db.add(new_user)
        db.commit()
    return {"status": "registered", "user_id": user_id}

@app.post("/auth/login")
async def Login(form_data: OAuth2PasswordRequestForm= Depends()):
    with get_db_context() as db:
        user = db.query(UserModel).filter(UserModel.user_id==form_data.username).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token(user_id=user.user_id)
    return {"access_token": token, "token_type": "bearer"}

# --- BASIC INGESTION ROUTES ---
@app.post("/chat/append")
async def append_message(message: ChatMessage):
    if message.role not in ["user", "assistant"]:
        raise HTTPException(status_code=400, detail="Invalid role, must be 'user' or 'assistant'")
    
    with get_db_context() as db:
        dbMessage = MessageModel(
            user_id = message.user_id, 
            session_id = message.session_id,
            role  = message.role,
            content = message.content
        )
        db.add(dbMessage)
        db.commit()
        
        count = db.query(MessageModel).filter(
            MessageModel.session_id == message.session_id,
            MessageModel.user_id == message.user_id
        ).count()
        
    return {
        "status": "Success",
        "session_id": message.session_id,
        "message_count": count
    }

# BUG 4 FIXED: Added current_user context dependency and isolated history queries by user_id
@app.get("/chat/buffer/{session_id}")
async def get_buffer(session_id: str, current_user: str = Depends(get_current_user)):
    with get_db_context() as db:
        messages = db.query(MessageModel).filter(
            MessageModel.session_id == session_id,
            MessageModel.user_id == current_user
        ).all()
        if not messages:
            raise HTTPException(status_code=404, detail="Session ID not found for this user context.")
        return [{"role": m.role, "content": m.content} for m in messages]


# --- FEATURE 1: CORE SYNTHESIS ENDPOINT ---
@app.post("/memory/update")
async def extract_pending_commitments(session_id : str, current_user: str = Depends(get_current_user)):
    with get_db_context() as db:
        messages = db.query(MessageModel).filter(
            MessageModel.session_id == session_id,
            MessageModel.user_id == current_user
        ).all()
        
        if not messages:
            raise HTTPException(status_code=404, detail="Session ID not found for this user context.")
        
        transcript_str = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
        user_record = db.query(UserModel).filter(UserModel.user_id == current_user).first()
        current_profile = json.loads(user_record.profile_json) if user_record and user_record.profile_json != "{}" else {
            "primary_goals": [],
            "psychological_constraints": [],
            "execution_style": {"preferred_pacing": "", "communication_preference": "", "vulnerabilities": []},
            "pending_commitments": []
        }
        
        system_instruction = (
        "Analyze the transcript between an engineer and their accountability partner. "
        "Identify specific behavioral friction points, anxieties, or bottlenecks. "
        "Do not alter the core user profile traits; output them cleanly as pending commitments."
        )
        
        try:
            extracted_profile: UserBehaviorProfile = instructor_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_model=UserBehaviorProfile,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Transcript:\n{transcript_str}"}
            ]
        )
        
            incoming_data = extracted_profile.model_dump()
            queue = current_profile.get("pending_commitments",[])
            
            for constraint in incoming_data.get("psychological_constraints", []):
                # 🛡️ DETERMINISTIC INJECTION (Bypasses LLM control entirely)
                constraint["confidence"] = 0.3
                constraint["times_observed"] = 1
                constraint["last_seen"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                constraint["detected_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                queue.append(constraint)
            
            user_record.profile_json = json.dumps(current_profile)
            current_profile["pending_commitments"] = queue
            
            db.commit()
            return {
            "status": "Commitments safely queued in temporary array",
            "pending_count": len(queue),
            "queued_items": queue
        }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Commitment extraction failed: {str(e)}")
       
@app.post("/memory/merge")
async def idempotent_profile_merge(current_user: str = Depends(get_current_user)):
    with get_db_context() as db:
        user_record =  db.query(UserModel).filter(UserModel.user_id ==current_user).first()
        if not user_record or user_record.profile_json == "{}":
            raise HTTPException(status_code=404, detail="No existing profile to merge with.")
        
        profile = json.loads(user_record.profile_json)
        pending_queue = profile.get("pending_commitments", [])     

        if not pending_queue:
            return {"status": "Ignored", "message": "Pending staging queue is empty. Nothing to merge."}
        
        active_constraints = [
            PsychologicalConstraint(**c) for c in profile.get("psychological_constraints", [])
        ]    
    
        merged_count = 0
        updated_count = 0 
        
        for raw_item in pending_queue:
            pending_item = PsychologicalConstraint(
                friction_trigger=raw_item.get("friction_trigger", ""),
                observed_cognitive_state=raw_item.get("observed_cognitive_state", ""),
                mitigation_instruction=raw_item.get("mitigation_instruction", "")
            )
            
            match_Found = False
            for active_item in active_constraints:
                if active_item.friction_trigger == pending_item.friction_trigger:
                    match_Found = True
                    updated_count += 1
                    active_item.reinforce_metric()
                    break

            if not match_Found:
                merged_count += 1
                active_constraints.append(pending_item)
            profile["psychological_constraints"] = [c.model_dump() for c in active_constraints]
            profile["pending_commitments"] = []
            
        user_record.profile_json = json.dumps(profile)
        db.commit()
        
        return {
            "status": "Success",
            "promoted_new_traits": merged_count,
            "reinforced_existing_traits": updated_count,
            "active_constraints_total": len(active_constraints)
        }
            
        # --- FEATURE 2: PROACTIVE CHECK-IN ROUTER ---
@app.post("/chat/proactive-checkin", response_model=ProactiveCheckInResponse)
async def generate_proactive_checkin(session_id: str, user_id: str = Depends(get_current_user) ):
    with get_db_context() as db:
        clean_user_id = user_id.strip()
        user_record = db.query(UserModel).filter(UserModel.user_id == clean_user_id).first()
        
        profile = json.loads(user_record.profile_json) if user_record else None
        
        if not profile or not profile.get("primary_goals"):
            fallback_greeting = "Welcome back. What is the single most critical milestone we are unblocking today?"
            # BUG 2 FIXED (PARTIAL): Tied fallback message directly to user_id
            db_message = MessageModel(user_id=clean_user_id, session_id=session_id, role="assistant", content=fallback_greeting)
            db.add(db_message)
            db.commit()
            return ProactiveCheckInResponse(opening_hook=fallback_greeting, rational_target="Default fallback setup.")
        
        system_instruction = (
            "You are a direct execution partner. Pick the SINGLE highest-priority "
            "unresolved item from the behavior graph. Ask one hyper-specific question "
            "about ONLY that item. Reference the exact task by name. "
            "Do not list multiple items. Do not soften with qualifiers. "
            "Max 2 sentences."
        )
        
        try:
            checkin_analysis: ProactiveCheckInResponse = instructor_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                response_model=ProactiveCheckInResponse,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"--- CURRENT LOGGED BEHAVIOR GRAPH ---\n{json.dumps(profile)}"}
                ]
            )
            
            # BUG 2 FIXED (PARTIAL): Tied assistant proactive check-in message to user_id
            db_message = MessageModel(user_id=clean_user_id, session_id=session_id, role="assistant", content=checkin_analysis.opening_hook)
            db.add(db_message)
            db.commit()
            
            return checkin_analysis
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to generate proactive check-in: {str(e)}")


# --- FEATURE 3 & 4: LIVE GUARDRAIL INTERCEPTION & SOCRATIC ENGINE ---
@app.post("/chat/respond")
async def generate_framed_response(session_id: str, payload: ChatRequestPayload, socratic_mode: bool = False, current_user: str = Depends(get_current_user)):
    with get_db_context() as db:
        # BUG 2 FIXED: Attached user_id context to inbound user message record
        user_message = MessageModel(user_id=current_user, session_id=session_id, role="user", content=payload.content)
        db.add(user_message)
        db.commit()
        
        user_record = db.query(UserModel).filter(UserModel.user_id == current_user).first()
        profile = json.loads(user_record.profile_json) if user_record else None
        
       
        
        goals = profile.get("primary_goals", []) or [] if profile else []
        constraints = profile.get("psychological_constraints", []) or [] if profile else []
        vulnerabilities = profile.get("execution_style", {}).get("vulnerabilities", []) if profile and isinstance(profile.get("execution_style"), dict) else []
        
        validated_constraints = [
        PsychologicalConstraint(**trait) for trait in constraints
        if trait.get("confidence", 0.3) >= 0.6        # ✅ dict-safe
]

# Dynamically construct system instructions from verified constraints only
        constraint_instructions = ""
        if validated_constraints:
            constraint_instructions = "\nCRITICAL VOICE ADAPTATION COMMANDS:\n"
            for constraint in validated_constraints:
                constraint_instructions += (
            f"- Trigger Condition: '{constraint.friction_trigger}' -> "
            f"Observed Behavioral Hazard: '{constraint.observed_cognitive_state}' -> "
            f"REQUIRED RESPONSE FORMAT: {constraint.mitigation_instruction}.\n"
            )
        else:
            constraint_instructions = "\nNo deeply verified behavioral traits established yet. Maintain a balanced, clear development tone."
        
        
        
        if socratic_mode:
            base_system_prompt = (
                "You are an aggressive, brutally honest Socratic interrogator. Your sole job is to "
                "ruthlessly audit user entries, call out absolute contradictions, identify logical gaps, "
                "and shred focus deviations from long-term trajectories. Do not sugarcoat anything. "
                "Challenge every weak assumption the user presents."
            )
        else:
            base_system_prompt = (
                "You are a highly supportive, collaborative engineering accountability buddy. Your goal is to "
                "help the user navigate complex engineering milestones through positive reinforcement, clear "
                "task breakdown structures, and encouraging guidance."
            )
        
        context_injection = "\n\n=== LIVE USER COGNITIVE PROFILE ==="
        
        if goals:
            context_injection += "\n🎯 KNOWN USER GOALS:\n" + "\n".join([f"- {g}" for g in goals])
        if vulnerabilities:
            context_injection += "\n🛑 CONFIRMED VULNERABILITIES:\n" + "\n".join([f"- {v}" for v in vulnerabilities])
        context_injection += "\n" + constraint_instructions
        
        context_injection += (
            "\n\n[STRICT RESPONSE RULES]:"
            "\n1. Your FIRST sentence must reference a specific item from the profile above by name."
            "\n2. You are FORBIDDEN from using these phrases: 'you are not alone', 'trust is a muscle', "
            "'you are more than your', 'it takes courage', 'that is something to be proud of', "
            "'one step at a time', 'you are capable'."
            "\n3. If the user describes a specific block, name that exact block back to them."
            "\n4. End every response with ONE specific action, not a list of three options."
            "\n5. Max 4 sentences total. No paragraphs. No life coaching."
        )
        base_system_prompt += context_injection
            
        compiled_messages = [{"role": "system", "content": base_system_prompt}]
        
        # BUG 1 FIXED: Isolated chat history retrieval to current_user AND session_id
        history = db.query(MessageModel).filter(
            MessageModel.session_id == session_id,
            MessageModel.user_id == current_user
        ).all()
        
        for msg in history:
            compiled_messages.append({"role": msg.role, "content": msg.content})
        
        try: 
            response = raw_groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=compiled_messages
            )
            
            assistant_text = response.choices[0].message.content
            
            # BUG 2 FIXED: Added user_id context to assistant message record
            assistant_msg = MessageModel(user_id=current_user, session_id=session_id, role="assistant", content=assistant_text)
            db.add(assistant_msg)
            db.commit()
            
            return {"response": assistant_text, "session_id": session_id}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Interception engine error: {str(e)}")


# --- FEATURE 5: ASYNCHRONOUS WORKSPACE SYNC ENGINE ---
# BUG 3 FIXED: Removed FastAPI's 'Depends' function from raw background thread execution context
def async_file_processor(content: str, user_id: str):
    try:
        print(f"⚙️ Background Thread Started: Ingesting file payload for user '{user_id}'...")
        
        system_instruction = (
            "You are an expert psychometric profiling parser. Read the user's uploaded raw text document, "
            "and extract their explicit goals, psychological vulnerabilities, and friction constraints "
            "into the exact schema structure required."
        )
        
        extracted_data: UserBehaviorProfile = instructor_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_model=UserBehaviorProfile,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Document Contents to analyze:\n{content}"}
            ]
        )
        
        incoming_map = extracted_data.model_dump()
        
        with get_db_context() as db:
            user_record = db.query(UserModel).filter(UserModel.user_id == user_id).first()
            if user_record:
                profile = json.loads(user_record.profile_json)
            else:
                profile = {
                    "primary_goals": [],
                    "psychological_constraints": [],
                    "execution_style": {"preferred_pacing": "Flexible", "communication_preference": "Direct", "vulnerabilities": []}
                }
            
            for goal in incoming_map.get("primary_goals", []):
                if goal not in profile["primary_goals"]:
                    profile["primary_goals"].append(goal)
                    
            new_vulnerabilities = incoming_map.get("execution_style", {}).get("vulnerabilities", [])
            for v in new_vulnerabilities:
                if v not in profile["execution_style"]["vulnerabilities"]:
                    profile["execution_style"]["vulnerabilities"].append(v)
                    
            profile["psychological_constraints"].extend(incoming_map.get("psychological_constraints", []))
            
            if user_record:
                user_record.profile_json = json.dumps(profile)
            else:
                user_record = UserModel(user_id=user_id, profile_json=json.dumps(profile))
                db.add(user_record)
                
            db.commit()
            print(f"✅ Background Ingestion Succeeded! Profile updated for user '{user_id}'.")
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print(f"❌ Async Ingestion Thread Crashed: {str(e)}")

@app.get("/chat/session/current")
async def get_rotated_context_session(current_user: str = Depends(get_current_user)):
    """
    🔄 Context Rotation Engine
    Generates a deterministic daily isolated session window identifier.
    """
    # Formats to: session_huzaif1a_2026-06-05
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    rotated_session_id = f"session_{current_user}_{today_str}"
    
    return {
        "status": "Context rotated successfully",
        "current_date": today_str,
        "active_session_id": rotated_session_id
    }
@app.post("/workspace/sync")
async def workspace_sync_endpoint(payload: dict, user_id: str = Depends(get_current_user)):
    file_text = payload.get("text", "")
    if not file_text:
        raise HTTPException(status_code=400, detail="Empty text payload received.")
        
    # The user_id string from FastAPI dependency injection passes perfectly as a simple argument here
    thread = threading.Thread(target=async_file_processor, args=(file_text, user_id))
    thread.start()
    
    return {"status": "processing", "message": "File dropped successfully. Analysis running."}

@app.get("/memory/profile")
async def get_profile(user_id: str = Depends(get_current_user)):
    with get_db_context() as db:
        rec = db.query(UserModel).filter(UserModel.user_id == user_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="No profile found for this user.")
        return json.loads(rec.profile_json)

@app.delete("/memory/profile")
async def reset_profile(user_id: str = Depends(get_current_user)):
    with get_db_context() as db:
        user_record = db.query(UserModel).filter(UserModel.user_id == user_id).first()
        if user_record:
            user_record.profile_json = "{}"
            db.commit()
    return {"status": "profile reset"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)