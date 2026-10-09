#include <cmath>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/IssueReporting.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/SwingTwistConstraint.h>
#include <Jolt/Physics/Constraints/HingeConstraint.h>

namespace Physics3D {

// -----------------------------------------------------------------------------

void writeVector(JPH::Vec3Arg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ();
}

void writeQuaternion(JPH::QuatArg value) {
    std::cout << ' ' << value.GetX() << ' ' << value.GetY() << ' ' << value.GetZ() << ' ' << value.GetW();
}

JPH::Quat swingTarget(float direction) {
    const float y = 0.1f * direction;
    const float z = -0.075f * direction;
    const auto swing = JPH::Quat(0, std::sin(y) * std::cos(z), std::cos(y) * std::sin(z), std::cos(y) * std::cos(z)).Normalized();
    return swing * JPH::Quat::sRotation(JPH::Vec3::sAxisX(), 0.25f * direction);
}

// -----------------------------------------------------------------------------

JPH::Vec3 hingeTorque(const JPH::HingeConstraint& joint, JPH::Vec3Arg firstAxis, JPH::Vec3Arg secondAxis, float delta) {
    const auto b = secondAxis.GetNormalizedPerpendicular();
    const auto c = secondAxis.Cross(b);
    const auto lambda = joint.GetTotalLambdaRotation();
    return (b.Cross(firstAxis) * lambda[0] + c.Cross(firstAxis) * lambda[1]
        + firstAxis * joint.GetTotalLambdaMotor()) / delta;
}

// -----------------------------------------------------------------------------

int runArticulatedPose(int mass, int rate, int side) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world;
    world.Init(16, 0, 16, 16, broadPhase, phaseFilter, pairFilter);
    auto physicsSettings = world.GetPhysicsSettings();
    physicsSettings.mNumVelocitySteps = 24;
    physicsSettings.mNumPositionSteps = 8;
    world.SetPhysicsSettings(physicsSettings);
    world.SetGravity(JPH::Vec3(0, -9.81f, 0));
    JPH::RefConst<JPH::SphereShape> shape = new JPH::SphereShape(0.25f);
    const auto base = JPH::Quat::sRotation(JPH::Vec3(1, 2, -1).Normalized(), 0.7f);
    const auto frame = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), 0.35f);
    const JPH::Vec3 upperLever(0.5f, 0.2f, 0.4f * side);
    const JPH::Vec3 elbowAnchor(0.5f, -0.2f, 0.15f * side);
    const JPH::Vec3 lowerLever(0.35f, 0.1f, -0.3f * side);
    auto& bodies = world.GetBodyInterface();
    const auto createBody = [&](JPH::Vec3Arg position, float bodyMass, float inertia) {
        JPH::BodyCreationSettings settings(shape, JPH::RVec3(position), base,
            bodyMass == 0 ? JPH::EMotionType::Static : JPH::EMotionType::Dynamic, 0);
        settings.mAllowSleeping = false;
        settings.mLinearDamping = settings.mAngularDamping = 0;
        if (bodyMass != 0) {
            settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
            settings.mMassPropertiesOverride.mMass = bodyMass;
            settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sScale(JPH::Vec3::sReplicate(inertia));
        }
        auto* body = bodies.CreateBody(settings);
        if (body) bodies.AddBody(body->GetID(), bodyMass == 0 ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
        return body;
    };
    auto* supportBody = createBody(JPH::Vec3::sZero(), 0, 0);
    auto* upperBody = createBody(base * upperLever, 2, 0.4f);
    auto* lowerBody = createBody(base * (upperLever + elbowAnchor + lowerLever), static_cast<float>(mass), 0.2f);
    if (!supportBody || !upperBody || !lowerBody) return 3;
    const auto support = supportBody->GetID();
    const auto upper = upperBody->GetID();
    const auto lower = lowerBody->GetID();
    JPH::SwingTwistConstraintSettings shoulderSettings;
    shoulderSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    shoulderSettings.mPosition1 = JPH::RVec3::sZero();
    shoulderSettings.mPosition2 = JPH::RVec3(-upperLever);
    shoulderSettings.mTwistAxis1 = shoulderSettings.mTwistAxis2 = frame * JPH::Vec3::sAxisX();
    shoulderSettings.mPlaneAxis1 = shoulderSettings.mPlaneAxis2 = frame * JPH::Vec3::sAxisZ();
    shoulderSettings.mPlaneHalfConeAngle = shoulderSettings.mNormalHalfConeAngle = 0.8f;
    shoulderSettings.mTwistMinAngle = -0.8f;
    shoulderSettings.mTwistMaxAngle = 0.8f;
    for (auto* motor : { &shoulderSettings.mTwistMotorSettings, &shoulderSettings.mSwingMotorSettings }) {
        motor->mMinTorqueLimit = -60;
        motor->mMaxTorqueLimit = 60;
        motor->mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 120, 20);
    }
    JPH::Ref<JPH::SwingTwistConstraint> shoulder = new JPH::SwingTwistConstraint(*supportBody, *upperBody, shoulderSettings);
    shoulder->SetTwistMotorState(JPH::EMotorState::Position);
    shoulder->SetSwingMotorState(JPH::EMotorState::Position);
    world.AddConstraint(shoulder.GetPtr());
    JPH::HingeConstraintSettings elbowSettings;
    elbowSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    elbowSettings.mPoint1 = JPH::RVec3(elbowAnchor);
    elbowSettings.mPoint2 = JPH::RVec3(-lowerLever);
    elbowSettings.mHingeAxis1 = elbowSettings.mHingeAxis2 = JPH::Vec3::sAxisZ();
    elbowSettings.mNormalAxis1 = elbowSettings.mNormalAxis2 = JPH::Vec3::sAxisX();
    elbowSettings.mLimitsMin = -0.8f;
    elbowSettings.mLimitsMax = 0.8f;
    elbowSettings.mMotorSettings.mMinTorqueLimit = -40;
    elbowSettings.mMotorSettings.mMaxTorqueLimit = 40;
    elbowSettings.mMotorSettings.mSpringSettings = JPH::SpringSettings(JPH::ESpringMode::StiffnessAndDamping, 80, 15);
    JPH::Ref<JPH::HingeConstraint> elbow = new JPH::HingeConstraint(*upperBody, *lowerBody, elbowSettings);
    elbow->SetMotorState(JPH::EMotorState::Position);
    world.AddConstraint(elbow.GetPtr());
    JPH::TempAllocatorImpl allocator(1024 * 1024);
    JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
    const float delta = 1.0f / rate;
    for (int step = 1; step <= rate * 12; ++step) {
        if (step == 1 || step == rate * 4 + 1 || step == rate * 8 + 1) {
            float direction = static_cast<float>(side);
            if (step > rate * 4) direction = -direction;
            if (step > rate * 8) direction = 0;
            shoulder->SetTargetOrientationCS(swingTarget(direction));
            elbow->SetTargetAngle(0.35f * direction);
            shoulder->ResetWarmStart();
            elbow->ResetWarmStart();
        }
        const auto bp1 = JPH::Vec3(bodies.GetPosition(upper));
        const auto bq1 = bodies.GetRotation(upper);
        const auto bv1 = bodies.GetLinearVelocity(upper);
        const auto bw1 = bodies.GetAngularVelocity(upper);
        const auto bp2 = JPH::Vec3(bodies.GetPosition(lower));
        const auto bq2 = bodies.GetRotation(lower);
        const auto bv2 = bodies.GetLinearVelocity(lower);
        const auto bw2 = bodies.GetAngularVelocity(lower);
        if (world.Update(delta, 1, &allocator, &jobs) != JPH::EPhysicsUpdateError::None) return 4;
        if (shoulder->GetTotalLambdaTwist() != 0 || shoulder->GetTotalLambdaSwingY() != 0
            || shoulder->GetTotalLambdaSwingZ() != 0 || elbow->GetTotalLambdaRotationLimits() != 0) return 5;
        const auto p1 = JPH::Vec3(bodies.GetPosition(upper));
        const auto q1 = bodies.GetRotation(upper);
        const auto w1 = bodies.GetAngularVelocity(upper);
        const auto p2 = JPH::Vec3(bodies.GetPosition(lower));
        const auto q2 = bodies.GetRotation(lower);
        const auto w2 = bodies.GetAngularVelocity(lower);
        const auto motor = shoulder->GetTotalLambdaMotor() / delta;
        std::cout << "articulatedpose " << mass << ' ' << rate << ' ' << side << ' ' << step;
        writeVector(bp1); writeQuaternion(bq1); writeVector(bv1); writeVector(bw1);
        writeVector(bp2); writeQuaternion(bq2); writeVector(bv2); writeVector(bw2);
        writeVector(p1); writeQuaternion(q1); writeVector(bodies.GetLinearVelocity(upper)); writeVector(w1);
        writeVector(p2); writeQuaternion(q2); writeVector(bodies.GetLinearVelocity(lower)); writeVector(w2);
        writeVector(shoulder->GetTotalLambdaPosition() / delta); writeVector((bq1 * frame) * motor);
        writeVector(elbow->GetTotalLambdaPosition() / delta);
        writeVector(hingeTorque(*elbow, bq1 * JPH::Vec3::sAxisZ(), bq2 * JPH::Vec3::sAxisZ(), delta));
        writeVector(motor); writeQuaternion(shoulder->GetRotationInConstraintSpace());
        writeVector((q1 * frame).Conjugated() * w1);
        writeVector(p1 - q1 * upperLever);
        writeVector(p2 - q2 * lowerLever - p1 - q1 * elbowAnchor);
        std::cout << ' ' << elbow->GetCurrentAngle() << ' ' << (q1 * JPH::Vec3::sAxisZ()).Dot(w2 - w1)
            << ' ' << elbow->GetTotalLambdaMotor() / delta << '\n';
    }
    world.RemoveConstraint(elbow.GetPtr());
    world.RemoveConstraint(shoulder.GetPtr());
    for (auto id : { lower, upper, support }) {
        bodies.RemoveBody(id);
        bodies.DestroyBody(id);
    }
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
    for (int mass : { 1, 2 }) for (int rate : { 60, 120 }) for (int side : { -1, 1 }) {
        if (result == 0) result = Physics3D::runArticulatedPose(mass, rate, side);
    }
    JPH::UnregisterTypes();
    JPH::Factory::sInstance = nullptr;
    return result;
}
