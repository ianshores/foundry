local root=assert(os.getenv("PD_REVIEW_ROOT"), "PD_REVIEW_ROOT is required")
local report=io.open(root.."/reaper-render-report.txt","w")
for _,kind in ipairs({"CLAP", "VST3"}) do
  reaper.Main_OnCommand(40023,0)
  reaper.InsertTrackAtIndex(0,false)
  local track=reaper.GetTrack(0,0)
  reaper.SetEditCurPos(0,false,false)
  reaper.InsertMedia(root.."/impulse.wav",0)
  local fx=reaper.TrackFX_AddByName(track,kind..": StereoDelay (Ian Shores)",false,-1)
  report:write(kind," instance: ",fx,"\n");report:flush()
  if fx<0 then report:close();return end
  local values={feedback=0.5/0.9,left_ms=99/1999,right_ms=149/1999,wet=1}
  for i=0,reaper.TrackFX_GetNumParams(track,fx)-1 do
    local ok,name=reaper.TrackFX_GetParamName(track,fx,i,"")
    report:write("  ",name,"\n");report:flush()
    if values[name:gsub(" ","_")] then reaper.TrackFX_SetParamNormalized(track,fx,i,values[name:gsub(" ","_")]) end
  end
  reaper.GetSetProjectInfo(0,"PROJECT_SRATE",48000,true)
  reaper.GetSetProjectInfo(0,"PROJECT_SRATE_USE",1,true)
  reaper.GetSetProjectInfo(0,"RENDER_SETTINGS",0,true)
  reaper.GetSetProjectInfo(0,"RENDER_BOUNDSFLAG",0,true)
  reaper.GetSetProjectInfo(0,"RENDER_STARTPOS",0,true)
  reaper.GetSetProjectInfo(0,"RENDER_ENDPOS",2,true)
  reaper.GetSetProjectInfo(0,"RENDER_SRATE",48000,true)
  reaper.GetSetProjectInfo(0,"RENDER_CHANNELS",2,true)
  reaper.GetSetProjectInfo(0,"RENDER_TAILFLAG",0,true)
  reaper.GetSetProjectInfo_String(0,"RENDER_FILE",root,true)
  reaper.GetSetProjectInfo_String(0,"RENDER_PATTERN","reaper-"..kind,true)
  reaper.GetSetProjectInfo_String(0,"RENDER_FORMAT","ZXZhdxgAAA==",true)
  reaper.Main_SaveProjectEx(0,root.."/review-"..kind..".rpp",8)
  reaper.Main_OnCommand(41824,0)
  reaper.Main_SaveProjectEx(0,root.."/review-"..kind..".rpp",8)
  report:write("Rendered ",kind,"\n");report:flush()
end
report:close()
reaper.Main_OnCommand(40004,0)
