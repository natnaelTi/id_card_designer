/* Serialized optimistic writes. Never replace edits made while a request is in flight. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.IDCardAutosave = api;
})(typeof window === 'undefined' ? globalThis : window, () => {
  class Journal {
    constructor(storage, key, secret) { this.storage=storage; this.key=key; this.secret=secret; this.chain=Promise.resolve();this.sequence=0; }
    async cipher() { return crypto.subtle.importKey('raw',Uint8Array.from(atob(this.secret),c=>c.charCodeAt(0)),{name:'AES-GCM'},false,['encrypt','decrypt']); }
    write(payload) {
      this.sequence++;this.chain=this.chain.catch(()=>{}).then(async()=>{
        const iv=crypto.getRandomValues(new Uint8Array(12));
        const bytes=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:new TextEncoder().encode(this.key)},await this.cipher(),new TextEncoder().encode(JSON.stringify({payload,expires:Date.now()+86400000})));
        this.storage.setItem(this.key,JSON.stringify({iv:Array.from(iv),bytes:Array.from(new Uint8Array(bytes))}));
      });return this.chain;
    }
    async read() {
      const raw=this.storage.getItem(this.key);if(!raw)return null;
      try {const record=JSON.parse(raw);const bytes=await crypto.subtle.decrypt({name:'AES-GCM',iv:new Uint8Array(record.iv),additionalData:new TextEncoder().encode(this.key)},await this.cipher(),new Uint8Array(record.bytes));const value=JSON.parse(new TextDecoder().decode(bytes));return value.expires>Date.now()?value.payload:null;}catch{return null;}
    }
    async clear(){const sequence=this.sequence;await this.chain.catch(()=>{});if(sequence===this.sequence)this.storage.removeItem(this.key);}
  }
  class Queue {
    constructor({save,onState=()=>{},onSaved=()=>{},journal=null,delay=700,online=()=>true}) {
      Object.assign(this,{save,onState,onSaved,journal,delay,online});this.version=0;this.saved=0;this.modified=null;this.pending=null;this.running=null;this.state='Saved';
    }
    setState(state,error=null){this.state=state;this.error=error;this.onState(state,error);}
    mark(payload){this.pending=structuredClone(payload);this.version++;this.persist=this.journal?.write(this.pending).catch(error=>{this.recoveryError=error;});const conflict=this.state==='Conflict';if(!conflict)this.setState(this.online()?'Unsaved':'Offline/Disconnected');clearTimeout(this.timer);if(!conflict)this.timer=setTimeout(()=>this.flush().catch(()=>{}),this.delay);}
    async flush(){
      clearTimeout(this.timer);if(this.running){await this.running;if(this.saved<this.version)return this.flush();return;}
      if(!this.pending||this.saved===this.version)return;
      if(this.state==='Conflict')throw this.error;
      if(!this.online()){this.setState('Offline/Disconnected');throw Error('Offline: encrypted draft retained.');}
      this.running=(async()=>{
        await this.persist;
        while(this.saved<this.version){
          const sent=this.version;const payload=structuredClone(this.pending);if(this.modified)payload.modified=this.modified;
          this.setState('Saving…');
          try{const result=await this.save(payload);this.modified=result.modified;this.saved=sent;this.pending.name=result.name;this.pending.modified=result.modified;await this.onSaved(result,sent===this.version);if(sent===this.version){await this.journal?.clear();this.setState('Saved');}}
          catch(error){const conflict=error?.responseJSON?.exc_type==='TimestampMismatchError'||error?.exc_type==='TimestampMismatchError';this.setState(conflict?'Conflict':this.online()?'Error':'Offline/Disconnected',error);throw error;}
        }
      })();try{await this.running;}finally{this.running=null;}
    }
    reset(doc){clearTimeout(this.timer);this.pending=null;this.version=this.saved=0;this.modified=doc.modified;this.setState('Saved');}
    dispose(){clearTimeout(this.timer);}
  }
  return {Queue,Journal};
});
