#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "GameFramework/Actor.h"
#include "GameFramework/HUD.h"
#include "GameFramework/GameModeBase.h"
#include "DelayReview.generated.h"
class USoundSubmix;
class USoundEffectSubmixPreset;
class USoundBase;
class UAudioComponent;
class ULevelStreaming;

// Holds the return asset for the lifetime of this game instance. The audio device
// owns its DSP instance; streamed level actors never own or recreate the return.
UCLASS()
class DELAYREVIEW_API UPdDelayReturnSubsystem : public UGameInstanceSubsystem {
 GENERATED_BODY()
public:
 virtual void Initialize(FSubsystemCollectionBase& Collection) override;
 UPROPERTY(BlueprintReadOnly, Category="PD Demo") TObjectPtr<USoundSubmix> DelayReturn;
 UPROPERTY() TObjectPtr<USoundEffectSubmixPreset> DelayPreset;
 void ActivateReturn(const UObject* WorldContext);
 bool bReturnActivated=false;
 UFUNCTION(BlueprintCallable, Category="PD Demo") void SendToDelay(UAudioComponent* Source, float Amount=1.f);
};

// Saved separately in Room_A.umap and Room_B.umap. Its component and voice die with that streamed level.
UCLASS()
class DELAYREVIEW_API APdRoomClickSource : public AActor {
 GENERATED_BODY()
public:
 APdRoomClickSource();
 UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PD Demo") TObjectPtr<UAudioComponent> Audio;
 void PlayIntoReturn();
 virtual void EndPlay(const EEndPlayReason::Type Reason) override;
};

UCLASS()
class DELAYREVIEW_API APdDelayDemo : public AActor {
 GENERATED_BODY()
public:
 APdDelayDemo();
 virtual void BeginPlay() override;
 virtual void Tick(float DeltaSeconds) override;
 UPROPERTY(EditAnywhere, Category="Separate MetaSound Demo", meta=(DisplayName="MetaSound Preview (Mode 2 Only)")) TObjectPtr<USoundBase> MetaClick;
 UPROPERTY(EditAnywhere, Category="Persistent Effects") TObjectPtr<USoundSubmix> SharedReturn;
 FString Status=TEXT("Loading first streamed level...");
 FString ActiveLevel=TEXT("Room_A");
 bool bMeta=false;
 float Clock=0;
 void SelectSubmix();
 void SelectMeta();
 void SendClick();
 void RestartCycle();
private:
 int32 Stage=0;
 float StageStart=0;
 int32 Cycle=0;
 bool bRecorded=false;
 bool bTest=false;
 bool bMetaTest=false;
 bool bOffline=false;
 bool bSawUnload=false;
 UPROPERTY() TObjectPtr<UAudioComponent> MetaComponent;
 TWeakObjectPtr<AActor> Emitter;
 ULevelStreaming* Stream(const FString& Name) const;
 void Mark(const FString& Event);
};

UCLASS()
class DELAYREVIEW_API APdDelayHUD : public AHUD {
 GENERATED_BODY()
public:
 virtual void DrawHUD() override;
};

UCLASS()
class DELAYREVIEW_API APdDemoGameMode : public AGameModeBase {
 GENERATED_BODY()
public:
 APdDemoGameMode();
};
