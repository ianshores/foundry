using UnrealBuildTool;
public class DelayReview : ModuleRules {
    public DelayReview(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","InputCore","AudioMixer","PdStereoDelay","NonRealtimeAudioRenderer"});
    }
}
