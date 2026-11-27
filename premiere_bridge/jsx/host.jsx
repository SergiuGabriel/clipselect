// MoneyMakingMachine bridge (Premiere side). Called by js/main.js when the app leaves a job.
// The adjustment layer + crop follows the owner's WarpAutomation panel (same steps, proven in Premiere 2026).
var MMMBridge = (function(){
  function js(o){
    if (o===null || o===undefined) return "null";
    var t=typeof o;
    if (t=="number" || t=="boolean") return String(o);
    if (t=="string") return '"'+o.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n").replace(/\r/g,"")+'"';
    var out=[], k;
    if (o instanceof Array){ for (k=0;k<o.length;k++) out.push(js(o[k])); return "["+out.join(",")+"]"; }
    for (k in o) out.push(js(String(k))+":"+js(o[k]));
    return "{"+out.join(",")+"}";
  }
  function walk(bin, depth, fn){
    for (var i=0;i<bin.children.numItems;i++){
      var it=bin.children[i];
      fn(it);
      if (it.type==2 && depth<6) walk(it, depth+1, fn);
    }
  }
  function info(){
    try{
      if (!app.project || !app.project.rootItem) return js({project:false});
      var pp=""; try{ pp=app.project.path; }catch(e){}
      return js({project:!!pp, path:pp||"", name:app.project.name||""});
    }catch(e){ return js({project:false, error:e.toString()}); }
  }
  function seqIds(){
    var ids={};
    for (var i=0;i<app.project.sequences.numSequences;i++) ids[app.project.sequences[i].sequenceID]=1;
    return ids;
  }
  // import the app's XML into the open project, open its sequence
  function importXml(path, name){
    try{
      if (!app.project || !app.project.rootItem) return js({ok:false, wait:true, msg:"No project is open in Premiere."});
      var f=new File(path);
      if (!f.exists) return js({ok:false, msg:"The XML is not on this computer: "+path});
      var before=seqIds();
      var ok=app.project.importFiles([f.fsName], true, app.project.rootItem, false);
      var seq=null, i, s;
      for (i=0;i<app.project.sequences.numSequences;i++){
        s=app.project.sequences[i];
        if (!before[s.sequenceID]){ if (!seq || s.name==name) seq=s; }
      }
      if (!seq) return js({ok:false, msg:"Premiere imported the XML but no new sequence appeared."});
      app.project.openSequence(seq.sequenceID);
      return js({ok:true, seq:seq.sequenceID, name:seq.name});
    }catch(e){ return js({ok:false, msg:"Import failed: "+e.toString()}); }
  }
  function adjItems(){
    var out=[];
    walk(app.project.rootItem, 0, function(it){ if (it.type!=2 && /^Adjustment Layer/i.test(it.name)) out.push(it); });
    return out;
  }
  function adjPrep(seqId){
    try{
      if (seqId){
        for (var i=0;i<app.project.sequences.numSequences;i++){
          var s=app.project.sequences[i];
          if (s.sequenceID==seqId){ app.project.openSequence(seqId); break; }
        }
      }
      if (!app.project.activeSequence) return js({ok:false, msg:"No active sequence."});
      var ids=[], l=adjItems();
      for (var k=0;k<l.length;k++) ids.push(l[k].nodeId);
      return js({ok:true, ids:ids.join(","), name:app.project.name||""});
    }catch(e){ return js({ok:false, msg:e.toString()}); }
  }
  function getProp(cl, comp, prop){
    for (var i=0;i<cl.components.numItems;i++){
      var c=cl.components[i];
      if (c.displayName==comp){
        for (var p=0;p<c.properties.numItems;p++){ if (c.properties[p].displayName==prop) return c.properties[p]; }
      }
    }
    return null;
  }
  function qeAt(seq, track, secs){
    var fr=1/25; try{ fr=Number(seq.timebase)/254016000000; if(!(fr>0)) fr=1/25; }catch(e){}
    var qeTr=qe.project.getActiveSequence().getVideoTrackAt(track), best=null, bd=1e9;
    for (var i=0;i<qeTr.numItems;i++){
      var q=qeTr.getItemAt(i);
      if (String(q.type)=="Empty") continue;
      var d=Math.abs(Number(q.start.secs)-secs);
      if (d<bd){ bd=d; best=q; }
    }
    return (best && bd<=fr*0.75) ? best : null;
  }
  function lastEnd(seq){
    var e=0, t, c;
    for (t=0;t<seq.videoTracks.numTracks;t++) for (c=0;c<seq.videoTracks[t].clips.numItems;c++) e=Math.max(e, seq.videoTracks[t].clips[c].end.seconds);
    for (t=0;t<seq.audioTracks.numTracks;t++) for (c=0;c<seq.audioTracks[t].clips.numItems;c++) e=Math.max(e, seq.audioTracks[t].clips[c].end.seconds);
    return e;
  }
  // the adjustment layer created just before (not in oldCsv) over the whole sequence, on an empty track above
  // everything, with Crop top / bottom
  function adjPlace(oldCsv, crop){
    try{
      app.enableQE();
      var seq=app.project.activeSequence;
      if (!seq) return js({ok:false, msg:"No active sequence."});
      var l=adjItems(), pi=null, old=","+oldCsv+",", i;
      for (i=0;i<l.length;i++) if (old.indexOf(","+l[i].nodeId+",")<0) pi=l[i];
      if (!pi) return js({ok:false, msg:"Couldn't find the new adjustment layer in the Project panel."});
      var endS=lastEnd(seq);
      if (endS<=0) return js({ok:false, msg:"The sequence is empty."});
      function topEmpty(){ for (var k=seq.videoTracks.numTracks-1;k>=0;k--){ if(seq.videoTracks[k].clips.numItems==0) return k; } return -1; }
      function aboveAll(k){ for (var m=k+1;m<seq.videoTracks.numTracks;m++){ if(seq.videoTracks[m].clips.numItems>0) return false; } return true; }
      var track=topEmpty();
      if (track<0 || !aboveAll(track)){
        try{ qe.project.getActiveSequence().addTracks(1, seq.videoTracks.numTracks, 0); }catch(e){}
        track=topEmpty();
      }
      if (track<0 || seq.videoTracks[track].clips.numItems>0) return js({ok:false, msg:"Couldn't add an empty video track on top."});
      seq.videoTracks[track].overwriteClip(pi, 0);
      var cl=seq.videoTracks[track].clips[0];
      if (!cl) return js({ok:false, msg:"Couldn't place the adjustment layer on the timeline."});
      try{ var T=new Time(); T.seconds=endS; cl.end=T; }catch(e){}
      cl=seq.videoTracks[track].clips[0];
      var note=(cl.end.seconds < endS-0.2) ? " The layer only covers "+Math.round(cl.end.seconds)+" s: drag its end to the end of the film." : "";
      try{ pi.name="MoneyMakingMachine crop"; }catch(e){}
      if (crop>0){
        var q=qeAt(seq, track, cl.start.seconds);
        if (!q) return js({ok:true, msg:"Adjustment layer on V"+(track+1)+", but Crop could not be added."+note});
        q.addVideoEffect(qe.project.getVideoEffectByName("Crop"));
        cl=seq.videoTracks[track].clips[0];
        var top=getProp(cl,"Crop","Top"), bot=getProp(cl,"Crop","Bottom");
        if (!top || !bot) return js({ok:true, msg:"Adjustment layer on V"+(track+1)+" with Crop, but Top / Bottom could not be set."+note});
        top.setValue(crop,true); bot.setValue(crop,true);
      }
      return js({ok:true, track:track+1, msg:"Adjustment layer on V"+(track+1)+" with Crop "+crop+" % top / bottom."+note});
    }catch(e){ return js({ok:false, msg:"Error: "+e.toString()}); }
  }
  return {info:info, importXml:importXml, adjPrep:adjPrep, adjPlace:adjPlace};
})();
