#include <cmath>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <numbers>
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/IssueReporting.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Constraints/HingeConstraint.h>
#include <Jolt/Physics/Constraints/SliderConstraint.h>
#include <Jolt/Physics/Constraints/RackAndPinionConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

int runRackServoCase(int rate, int caseId) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto options = world.GetPhysicsSettings();
    options.mNumVelocitySteps = 12;
    options.mNumPositionSteps = 4;
    world.SetPhysicsSettings(options);
    world.SetGravity(JPH::Vec3::sZero());
    auto& bodies = world.GetBodyInterface();
    auto makeBody = [&](JPH::Vec3 position, JPH::Vec3 halfSize, JPH::EMotionType type) {
        JPH::RefConst<JPH::BoxShape> shape = new JPH::BoxShape(halfSize);
        JPH::BodyCreationSettings settings(shape, JPH::RVec3(position), JPH::Quat::sIdentity(), type, 0);
        settings.mAllowSleeping = false;
        settings.mLinearDamping = settings.mAngularDamping = 0;
        settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
        settings.mMassPropertiesOverride.mMass = 2;
        settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(0.4f));
        return bodies.CreateAndAddBody(settings, type == JPH::EMotionType::Static ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
    };
    const auto pinion = makeBody(JPH::Vec3(0, 2.4f, 0), JPH::Vec3(0.55f, 0.1f, 0.15f), JPH::EMotionType::Dynamic);
    const auto pivot = makeBody(JPH::Vec3(0, 2.4f, 0), JPH::Vec3::sReplicate(0.1f), JPH::EMotionType::Static);
    const auto rack = makeBody(JPH::Vec3(0, 1.8f, 0), JPH::Vec3(1.5f, 0.1f, 0.175f), JPH::EMotionType::Dynamic);
    const auto rail = makeBody(JPH::Vec3(0, 1.8f, 0), JPH::Vec3::sReplicate(0.1f), JPH::EMotionType::Static);
    if (pinion.IsInvalid() || pivot.IsInvalid() || rack.IsInvalid() || rail.IsInvalid()) return 3;
    JPH::HingeConstraintSettings hingeSettings;
    hingeSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    hingeSettings.mHingeAxis1 = hingeSettings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    hingeSettings.mNormalAxis1 = hingeSettings.mNormalAxis2 = JPH::Vec3::sAxisX();
    hingeSettings.mMotorSettings.SetTorqueLimit(12);
    hingeSettings.mMotorSettings.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 15, 8);
    JPH::Ref<JPH::HingeConstraint> driver = static_cast<JPH::HingeConstraint*>(bodies.CreateConstraint(&hingeSettings, pivot, pinion));
    world.AddConstraint(driver.GetPtr());
    JPH::SliderConstraintSettings sliderSettings;
    sliderSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    sliderSettings.mAutoDetectPoint = false;
    sliderSettings.mSliderAxis1 = sliderSettings.mSliderAxis2 = JPH::Vec3::sAxisX();
    sliderSettings.mNormalAxis1 = sliderSettings.mNormalAxis2 = JPH::Vec3::sAxisY();
    const float extent = caseId == 2 ? 0.6f : 1.1f;
    { sliderSettings.mLimitsMin = -extent; sliderSettings.mLimitsMax = extent; }
    JPH::Ref<JPH::SliderConstraint> guide = static_cast<JPH::SliderConstraint*>(bodies.CreateConstraint(&sliderSettings, rail, rack));
    world.AddConstraint(guide.GetPtr());
    JPH::RackAndPinionConstraintSettings couplingSettings;
    couplingSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    couplingSettings.mHingeAxis = JPH::Vec3::sAxisZ();
    couplingSettings.mSliderAxis = JPH::Vec3::sAxisX();
    couplingSettings.mRatio = 2;
    JPH::Ref<JPH::RackAndPinionConstraint> coupling = static_cast<JPH::RackAndPinionConstraint*>(bodies.CreateConstraint(&couplingSettings, pinion, rack));
    coupling->SetConstraints(driver.GetPtr(), guide.GetPtr());
    world.AddConstraint(coupling.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float amplitude = caseId == 0 ? 2.0f : 1.5f;
    float accumulatedAngle = 0;
    float previousAngle = 0;
    for (int phase = 0; phase < 2; ++phase) {
        const float target = phase == 0 ? amplitude : -amplitude;
        driver->SetTargetAngle(target);
        driver->SetMotorState(JPH::EMotorState::Position);
        for (int step = 0; step < rate * 3; ++step) {
            if (world.Update(1.0f / rate, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
            const auto orientation = bodies.GetRotation(pinion);
            const float angle = std::remainder(2 * std::atan2(orientation.GetZ(), orientation.GetW()), 2 * std::numbers::pi_v<float>);
            accumulatedAngle += std::remainder(angle - previousAngle, 2 * std::numbers::pi_v<float>);
            previousAngle = angle;
            const float travel = bodies.GetPosition(rack).GetX();
            const float phaseError = accumulatedAngle - 2 * travel;
            const float speed = bodies.GetAngularVelocity(pinion).GetZ();
            const float speedError = speed - 2 * bodies.GetLinearVelocity(rack).GetX();
            std::cout << "servo " << rate << ' ' << caseId << ' ' << phase << ' ' << step << ' ' << target << ' ' << angle << ' ' << accumulatedAngle << ' ' << travel << ' ' << phaseError << ' ' << speedError << ' ' << speed << ' ' << driver->GetTotalLambdaMotor() * rate << ' ' << coupling->GetTotalLambda() * rate << ' ' << -2 * coupling->GetTotalLambda() * rate << '\n';
        }
    }
    world.RemoveConstraint(coupling.GetPtr());
    world.RemoveConstraint(guide.GetPtr());
    world.RemoveConstraint(driver.GetPtr());
    for (const auto id : {pinion, pivot, rack, rail}) { bodies.RemoveBody(id); bodies.DestroyBody(id); }
    return 0;
}

// -----------------------------------------------------------------------------

} // namespace Physics3D

int main() {
#ifdef JPH_ENABLE_ASSERTS
    JPH::AssertFailed = [](const char* expression, const char* message, const char* file, JPH::uint line) {
        std::cerr << "Jolt assertion: " << expression << " at " << file << ':' << line << " message=" << (message ? message : "") << '\n';
        std::abort();
        return false;
    };
#endif
    JPH::RegisterDefaultAllocator();
    auto factory = std::make_unique<JPH::Factory>();
    JPH::Factory::sInstance = factory.get();
    JPH::RegisterTypes();
    std::cout.precision(9);
    int result = 0;
    for (const int rate : {60, 120}) {
        for (int caseId = 0; caseId < 3 && result == 0; ++caseId) result = Physics3D::runRackServoCase(rate, caseId);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
