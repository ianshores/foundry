#include "DelayReview.h"
#include "Modules/ModuleManager.h"
#include "Components/AudioComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/LevelStreaming.h"
#include "Engine/Level.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Sound/SoundSubmix.h"
#include "GameFramework/PlayerController.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/PackageName.h"
#include "Misc/CommandLine.h"
#include "HAL/PlatformMisc.h"
#include "AudioMixerDevice.h"
#include "AudioMixerPlatformNonRealtime.h"
#include "Misc/App.h"
#include "HAL/IConsoleManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, DelayReview, "DelayReview");

void UPdDelayReturnSubsystem::Initialize(FSubsystemCollectionBase& Collection) {
 Super::Initialize(Collection);
 // Defer audio asset loading until a playable world/audio device exists.
}
void UPdDelayReturnSubsystem::ActivateReturn(const UObject* WorldContext){
 if(bReturnActivated)return;
 DelayReturn=LoadObject<USoundSubmix>(nullptr,TEXT("/Game/PDReview/SM_PersistentDelayReturn.SM_PersistentDelayReturn"));
 DelayPreset=LoadObject<USoundEffectSubmixPreset>(nullptr,TEXT("/Game/PDReview/PD_StereoDelayReturn.PD_StereoDelayReturn"));
 check(DelayReturn && DelayPreset);
 TArray<USoundEffectSubmixPreset*> Chain{DelayPreset.Get()};
 UAudioMixerBlueprintLibrary::SetSubmixEffectChainOverride(WorldContext,DelayReturn,Chain,0.f);
 bReturnActivated=true;
 UE_LOG(LogTemp,Display,TEXT("PD_DEMO: Activated GameInstance-held persistent submix chain once: %p"),DelayReturn.Get());
}
void UPdDelayReturnSubsystem::SendToDelay(UAudioComponent* Source,float Amount) {
 if(!Source)return;
 ActivateReturn(Source);
 Source->SetSubmixSend(DelayReturn, FMath::Clamp(Amount,0.f,1.f));
}
APdRoomClickSource::APdRoomClickSource(){
 Audio=CreateDefaultSubobject<UAudioComponent>(TEXT("Room_Click_Audio"));
 SetRootComponent(Audio);
 Audio->bAutoActivate=false;Audio->bAutoDestroy=false;
 Audio->bStopWhenOwnerDestroyed=true;Audio->bAllowSpatialization=false;
}
void APdRoomClickSource::PlayIntoReturn(){
 GetGameInstance()->GetSubsystem<UPdDelayReturnSubsystem>()->SendToDelay(Audio);
 Audio->Play();
}
void APdRoomClickSource::EndPlay(const EEndPlayReason::Type Reason){
 const bool WasPlaying=Audio->IsPlaying();
 Super::EndPlay(Reason);
 UE_LOG(LogTemp,Display,TEXT("PD_ROOM_SOURCE_ENDPLAY level=%s reason=%d was_playing=%d"),*GetLevel()->GetOutermost()->GetName(),int32(Reason),WasPlaying);
}
APdDelayDemo::APdDelayDemo() { PrimaryActorTick.bCanEverTick=true; }
ULevelStreaming* APdDelayDemo::Stream(const FString& Name) const {
 return UGameplayStatics::GetStreamingLevel(this,FName(*Name));
}
void APdDelayDemo::Mark(const FString& Event) {
 const FString Line=FString::Printf(TEXT("%.3f %s\n"),Clock,*Event);
 UE_LOG(LogTemp,Display,TEXT("PD_DEMO %s"),*Line);
 FFileHelper::SaveStringToFile(Line,*(FPaths::ProjectSavedDir()/TEXT("PD-Demo-Timeline.txt")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
}
void APdDelayDemo::BeginPlay() {
 Super::BeginPlay();
 GetGameInstance()->GetSubsystem<UPdDelayReturnSubsystem>()->ActivateReturn(this);
 check(SharedReturn==GetGameInstance()->GetSubsystem<UPdDelayReturnSubsystem>()->DelayReturn);
 IFileManager::Get().Delete(*(FPaths::ProjectSavedDir()/TEXT("PD-Demo-Complete.txt")));
 FApp::SetUnfocusedVolumeMultiplier(1.f);
 bOffline=FParse::Param(FCommandLine::Get(),TEXT("PdOfflineAudio"));
 if(bOffline){
  IConsoleManager::Get().FindConsoleVariable(TEXT("au.nrt.RenderEveryTick"))->Set(0);
  FApp::SetUseFixedTimeStep(true);FApp::SetFixedDeltaTime(1.0/60.0);
 }
 bTest=FParse::Param(FCommandLine::Get(),TEXT("PdDemoTest"));
 FFileHelper::SaveStringToFile(TEXT("Persistent return / real streamed-level lifetime test\n"),*(FPaths::ProjectSavedDir()/TEXT("PD-Demo-Timeline.txt")));
 auto* PC=GetWorld()->GetFirstPlayerController();
 if(PC){
  EnableInput(PC);
  InputComponent->BindKey(EKeys::One,IE_Pressed,this,&APdDelayDemo::SelectSubmix);
  InputComponent->BindKey(EKeys::Two,IE_Pressed,this,&APdDelayDemo::SelectMeta);
  InputComponent->BindKey(EKeys::SpaceBar,IE_Pressed,this,&APdDelayDemo::SendClick);
  InputComponent->BindKey(EKeys::R,IE_Pressed,this,&APdDelayDemo::RestartCycle);
 }
 bMetaTest=FParse::Param(FCommandLine::Get(),TEXT("PdMetaDemoTest"));
 if(bMetaTest){UAudioMixerBlueprintLibrary::StartRecordingOutput(this,14.f);SelectMeta();}
 else SelectSubmix();
}
void APdDelayDemo::SelectSubmix(){
 bMeta=false;
 if(MetaComponent){MetaComponent->Stop();MetaComponent->DestroyComponent();MetaComponent=nullptr;}
 RestartCycle();
}
void APdDelayDemo::SelectMeta(){
 bMeta=true;
 if(!MetaComponent){MetaComponent=NewObject<UAudioComponent>(this);MetaComponent->bAutoActivate=false;MetaComponent->bAllowSpatialization=false;MetaComponent->RegisterComponent();MetaComponent->SetSound(MetaClick);}
 MetaComponent->Play();
 Status=TEXT("MetaSound: a short click every 4 seconds, through the PD delay node.");
 Mark(TEXT("METASOUND_CLICK_DEMO"));
}
void APdDelayDemo::RestartCycle(){
 if(bMeta) return;
 for(const auto& Name:{TEXT("Room_A"),TEXT("Room_B")}) if(auto* L=Stream(Name)){L->SetShouldBeVisible(false);L->SetShouldBeLoaded(false);}
 ActiveLevel=TEXT("Room_A");Stage=0;StageStart=Clock;
}
void APdDelayDemo::SendClick(){
 if(bMeta) return;
 auto* L=Stream(ActiveLevel);
 if(!L || !L->GetLoadedLevel()) return;
 APdRoomClickSource* SourceActor=nullptr;
 for(TActorIterator<APdRoomClickSource> It(GetWorld());It;++It){
  if(It->GetLevel()==L->GetLoadedLevel()){SourceActor=*It;break;}
 }
 if(!SourceActor){Status=TEXT("Waiting for the room's placed sound source.");return;}
 check(SourceActor->GetLevel()!=GetLevel());
 Emitter=SourceActor;
 SourceActor->PlayIntoReturn();
 const FString SourceLevel=FPackageName::GetShortName(SourceActor->GetLevel()->GetOutermost());
 const FString ControllerLevel=FPackageName::GetShortName(GetLevel()->GetOutermost());
 check(SourceLevel==ActiveLevel && ControllerLevel==TEXT("PersistentDemo"));
 Mark(TEXT("PLACED_ROOM_SOURCE owner_level=")+SourceLevel+TEXT(" controller_level=")+ControllerLevel+TEXT(" actor=")+SourceActor->GetPathName()+FString::Printf(TEXT(" pitch=%.3f"),SourceActor->Audio->PitchMultiplier));
 Mark(TEXT("CLICK source-owned-by-")+ActiveLevel+TEXT(" actor=")+SourceActor->GetPathName()+FString::Printf(TEXT(" component_playing=%d"),SourceActor->Audio->IsPlaying()));
}
void APdDelayDemo::Tick(float DeltaSeconds){
 Super::Tick(DeltaSeconds);Clock+=DeltaSeconds;
 if(bOffline){
  auto* Mixer=static_cast<Audio::FMixerDevice*>(GetWorld()->GetAudioDeviceRaw());
  static_cast<Audio::FMixerPlatformNonRealtime*>(Mixer->GetAudioMixerPlatform())->RenderAudio(DeltaSeconds);
 }
 if(bMeta){
  if(bMetaTest && Clock>10.f && !bRecorded){
   UAudioMixerBlueprintLibrary::StopRecordingOutput(this,EAudioRecordingExportType::WavFile,TEXT("MetaSoundClickDelay"),FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()/TEXT("BouncedWavFiles")));
   bRecorded=true;
  }
  if(bMetaTest && Clock>12.f)FPlatformMisc::RequestExit(false);
  return;
 }
 auto* Return=GetGameInstance()->GetSubsystem<UPdDelayReturnSubsystem>()->DelayReturn.Get();
 if(!bRecorded && Clock>.5f){
  UAudioMixerBlueprintLibrary::StartRecordingOutput(this,32.f,Return);
  bRecorded=true;Mark(TEXT("RECORD_RETURN_STARTED"));
 }
 auto* L=Stream(ActiveLevel);
 if(!L){Status=TEXT("Missing streamed level: ")+ActiveLevel;return;}
 switch(Stage){
 case 0:
  L->SetShouldBeLoaded(true);L->SetShouldBeVisible(true);
  Status=TEXT("Loading ")+ActiveLevel;Stage=1;break;
 case 1:
  if(L->IsLevelLoaded() && L->IsLevelVisible()){
   Mark(TEXT("LEVEL_VISIBLE ")+ActiveLevel);Stage=2;StageStart=Clock;
   Status=ActiveLevel+TEXT(" loaded. Its own pitched click will feed the shared delay return.");
  }break;
 case 2:
  if(Clock-StageStart>2.f){SendClick();Stage=3;StageStart=Clock;Status=TEXT("Click sent! Unloading its level before the first echo...");}break;
 case 3:
  if(Clock-StageStart>.35f){
   if(auto* SourceActor=Cast<APdRoomClickSource>(Emitter.Get())){
    check(SourceActor->Audio->IsPlaying());
    Mark(TEXT("LOOPING_SOURCE_UNLOADED_WHILE_PLAYING"));
   }
   L->SetShouldBeVisible(false);L->SetShouldBeLoaded(false);
   Mark(TEXT("UNLOAD_REQUEST ")+ActiveLevel);Stage=4;
  }break;
 case 4:
  if(!L->IsLevelLoaded() && !L->GetLoadedLevel()){
   if(Emitter.IsValid()){GEngine->ForceGarbageCollection(true);break;}
   const bool Gone=!Emitter.IsValid();
   Mark(FString::Printf(TEXT("LEVEL_UNLOADED %s emitter_destroyed=%d return=%p"),*ActiveLevel,Gone,Return));
   bSawUnload|=Gone;
   ActiveLevel=ActiveLevel==TEXT("Room_A")?TEXT("Room_B"):TEXT("Room_A");
   if(auto* Next=Stream(ActiveLevel)){Next->SetShouldBeLoaded(true);Next->SetShouldBeVisible(true);}
   Stage=5;StageStart=Clock;
   Status=TEXT("Source level unloaded; source destroyed. Hear its echoes while the next room loads.");
  }break;
 case 5:
  if(L->IsLevelLoaded() && L->IsLevelVisible()){
   Mark(TEXT("NEXT_LEVEL_VISIBLE ")+ActiveLevel);
   Status=ActiveLevel+TEXT(" loaded. The previous room's delay tail is still ringing.");Stage=6;
  }break;
 case 6:
  if(Clock-StageStart>9.f){Stage=2;StageStart=Clock;++Cycle;}break;
 }
 if(bRecorded && Clock>29.f && !FPaths::FileExists(FPaths::ProjectSavedDir()/TEXT("PD-Demo-Complete.txt"))){
  UAudioMixerBlueprintLibrary::StopRecordingOutput(this,EAudioRecordingExportType::WavFile,TEXT("PersistentDelayReturn"),FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()/TEXT("BouncedWavFiles")),Return);
  Mark(FString::Printf(TEXT("RECORD_FINISHED cycles=%d actual_source_destruction=%d"),Cycle,bSawUnload));
  FFileHelper::SaveStringToFile(bSawUnload?TEXT("PASS: actual streamed source destruction observed"):TEXT("FAIL: no source destruction"),*(FPaths::ProjectSavedDir()/TEXT("PD-Demo-Complete.txt")));
 }
 if(bTest && Clock>32.f){FPlatformMisc::RequestExit(false);}
}
void APdDelayHUD::DrawHUD(){
 Super::DrawHUD();if(!Canvas)return;
 APdDelayDemo* Demo=nullptr;for(TActorIterator<APdDelayDemo> It(GetWorld());It;++It){Demo=*It;break;}if(!Demo)return;
 const float W=Canvas->ClipX;
 DrawRect(FLinearColor(.025f,.035f,.065f,1),0,0,W,Canvas->ClipY);
 float Y=70;
 auto Line=[&](const FString& Text,FLinearColor Color,float Scale=1.1f){DrawText(Text,Color,60,Y,GEngine->GetMediumFont(),Scale);Y+=42;};
 Line(TEXT("PD / STEREO DELAY"),FLinearColor(.35f,.8f,1),2.f);Y+=25;
 Line(Demo->bMeta?TEXT("02   METASOUND CLICK DEMO"):TEXT("01   PERSISTENT SUBMIX / LEVEL STREAMING"),FLinearColor::White,1.4f);Y+=20;
 Line(TEXT("1  Submix transition demo      2  MetaSound click demo"),FLinearColor(.7f,.75f,.85f));
 Line(TEXT("SPACE  Trigger current room source      R  Replay A -> B transition"),FLinearColor(.7f,.75f,.85f));Y+=25;
 Line(Demo->Status,FLinearColor(.5f,1,.65f));Y+=15;
 if(!Demo->bMeta){
  for(const auto& Name:{TEXT("Room_A"),TEXT("Room_B")}){
   auto* L=UGameplayStatics::GetStreamingLevel(Demo,FName(Name));
   Line(FString(Name)+TEXT(" : ")+(L && L->IsLevelLoaded()?TEXT("LOADED"):TEXT("UNLOADED")),FLinearColor::White);
  }
  Y+=20;
  Line(TEXT("Each room owns its sound actor -> send -> persistent shared delay return"),FLinearColor(.7f,.8f,1));
  Line(TEXT("GameInstance holds return | PD plugin 100% wet | 700 / 1050 ms | feedback 0.72"),FLinearColor(.7f,.8f,1));
  Line(TEXT("Room A: LOW click (0.5x pitch) | Room B: HIGH click (2.0x pitch)"),FLinearColor(.7f,.8f,1));
 }
 else{Line(TEXT("Short click + silence -> Wave Player -> compiled PD delay -> stereo output"),FLinearColor(.7f,.8f,1));Line(TEXT("Open MS_ClickDelay in Content/PDReview to inspect and adjust the four controls."),FLinearColor(.7f,.8f,1));}
}

APdDemoGameMode::APdDemoGameMode(){HUDClass=APdDelayHUD::StaticClass();DefaultPawnClass=nullptr;}
