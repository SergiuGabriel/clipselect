// MoneyMakingMachine bridge: the app leaves jobs (JSON) in a folder, this picks them up inside Premiere.
// Two copies can run (the visible panel and the invisible worker): a job is claimed by renaming it, so only one runs it.
(function(){
  var cs=window.__adobe_cep__;
  var st=document.getElementById("st");
  function say(t){ if(st) st.textContent=t; }
  if (typeof require==="undefined"){ say("Node.js is not enabled: reinstall the bridge from MoneyMakingMachine > Settings."); return; }
  var fs=require("fs"), path=require("path"), os=require("os"), cp=require("child_process");
  var BASE=process.platform==="win32" ? path.join(process.env.APPDATA||os.homedir(), "MoneyMakingMachine Bridge")
                                        : path.join(os.homedir(), "Library", "Application Support", "MoneyMakingMachine Bridge");
  var JOBS=path.join(BASE,"jobs"), DONE=path.join(BASE,"done");
  try{ fs.mkdirSync(JOBS,{recursive:true}); fs.mkdirSync(DONE,{recursive:true}); }catch(e){}
  try{ fs.writeFileSync(path.join(BASE,"alive"), String(Date.now())); }catch(e){}
  var busy=false;
  // a job left half-done by a closed Premiere (claimed more than 15 min ago) is put back
  try{ fs.readdirSync(JOBS).forEach(function(f){ if(/\.run$/.test(f)){ var x=path.join(JOBS,f); if(Date.now()-fs.statSync(x).mtimeMs>900000) fs.renameSync(x, x.replace(/\.run$/,".json")); } }); }catch(e){}

  function ev(code){ return new Promise(function(res){ cs.evalScript(code, function(r){ var o=null; try{ o=JSON.parse(r); }catch(e){ o={ok:false,msg:String(r)}; } res(o); }); }); }
  function q(s){ return '"'+String(s).replace(/\\/g,"\\\\").replace(/"/g,'\\"')+'"'; }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r,ms); }); }
  function finish(id, o){
    try{ fs.writeFileSync(path.join(DONE,id+".json"), JSON.stringify(o)); }catch(e){}
    say((o.ok?"Done: ":"Problem: ")+(o.msg||""));
  }
  // File > New > Adjustment Layer through the menu (no scripting API for it); Premiere first, the Project panel focused
  function newAdjLayer(pname){
    return new Promise(function(res){
      if (process.platform!=="darwin"){ res("Windows: create File > New > Adjustment Layer by hand."); return; }
      var L=['tell application "System Events"',
        'set p to first process whose name starts with "Adobe Premiere Pro"',
        'set frontmost of p to true','delay 0.5','tell p',
        'try','click menu item '+q(pname)+' of menu 1 of menu item "Projects" of menu 1 of menu bar item "Window" of menu bar 1',
        'on error','try','click menu item '+q(pname+".prproj")+' of menu 1 of menu item "Projects" of menu 1 of menu bar item "Window" of menu bar 1','end try','end try',
        'delay 0.5',
        'set mi to (first menu item of menu 1 of menu item "New" of menu 1 of menu bar item "File" of menu bar 1 whose name starts with "Adjustment Layer")',
        'if not (enabled of mi) then return "OFF"',
        'click mi',
        'set n0 to count of windows',
        'repeat 40 times','delay 0.1','if (count of windows) > n0 then exit repeat','end repeat',
        'delay 0.3','keystroke return','return "OK"','end tell','end tell'];
      var a=[]; L.forEach(function(l){ a.push("-e"); a.push(l); });
      cp.execFile("/usr/bin/osascript", a, function(err, out, se){
        if (err){ res("macOS: "+String(se||err.message).trim()); return; }
        res(String(out).trim()==="OK" ? "" : "Premiere kept File > New > Adjustment Layer greyed out.");
      });
    });
  }
  async function runJob(id, job){
    var seq=null, msg=[];
    if (job.xml){
      say("Importing "+path.basename(job.xml)+"…");
      var r=await ev("MMMBridge.importXml("+q(job.xml)+","+q(job.name||"")+")");
      if (!r || !r.ok) return r && r.wait ? null : {ok:false, msg:(r&&r.msg)||"Import failed."};
      seq=r.seq; msg.push("Imported \""+r.name+"\".");
      await sleep(800);
    }
    if (job.adjust){
      say("Adjustment layer + crop…");
      var p=await ev("MMMBridge.adjPrep("+q(seq||"")+")");
      if (!p || !p.ok) return {ok:false, msg:msg.concat([(p&&p.msg)||"No sequence."]).join(" ")};
      var e=await newAdjLayer(p.name);
      if (e) return {ok:false, msg:msg.concat([e, "Use WarpAutomation's Adjustment layer + crop 10% button instead."]).join(" ")};
      await sleep(900);
      var a=await ev("MMMBridge.adjPlace("+q(p.ids)+","+Number(job.adjust.crop||0)+")");
      msg.push(a.msg||"");
      if (!a.ok) return {ok:false, msg:msg.join(" ")};
    }
    return {ok:true, msg:msg.join(" ")};
  }
  async function tick(){
    if (busy) return;
    busy=true;
    try{
      try{ fs.writeFileSync(path.join(BASE,"alive"), String(Date.now())); }catch(e){}
      var files=fs.readdirSync(JOBS).filter(function(f){ return /\.json$/.test(f); }).sort();
      for (var i=0;i<files.length;i++){
        var src=path.join(JOBS,files[i]), run=src.replace(/\.json$/,".run");
        try{ fs.renameSync(src, run); }catch(e){ continue; }      // the other copy took it
        var id=files[i].replace(/\.json$/,""), job=null;
        try{ job=JSON.parse(fs.readFileSync(run,"utf8")); }catch(e){ finish(id,{ok:false,msg:"Unreadable job."}); try{ fs.unlinkSync(run); }catch(e2){} continue; }
        var info=await ev("MMMBridge.info()");
        if (!info || !info.project){ fs.renameSync(run, src); say("Open a project in Premiere: MoneyMakingMachine is waiting to import "+path.basename(job.xml||"")); continue; }
        var res;
        try{ res=await runJob(id, job); }catch(e){ res={ok:false, msg:String(e)}; }
        if (res===null){ fs.renameSync(run, src); continue; }
        finish(id, res);
        try{ fs.unlinkSync(run); }catch(e){}
      }
    }catch(e){ say("Bridge error: "+e); }
    busy=false;
  }
  setInterval(tick, 1500);
  tick();
})();
