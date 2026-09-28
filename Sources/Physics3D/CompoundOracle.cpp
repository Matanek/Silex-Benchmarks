#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/CollisionDispatch.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <iostream>
#include <numbers>
#include <string_view>

namespace Physics3D {

int run_case() {
    JPH::RefConst<JPH::SphereShape> sphere = new JPH::SphereShape(0.5f);
    JPH::StaticCompoundShapeSettings settings;
    settings.AddShape(JPH::Vec3(-2.0f, 0.0f, 0.0f),
                      JPH::Quat::sIdentity(), sphere.GetPtr(), 11);
    settings.AddShape(JPH::Vec3(2.0f, 0.0f, 0.0f),
                      JPH::Quat::sIdentity(), sphere.GetPtr(), 22);
    JPH::RefConst<JPH::Shape> compoundShape = settings.Create().Get();
    if (compoundShape == nullptr) return 3;
    const auto* compound = static_cast<const JPH::StaticCompoundShape*>(
        compoundShape.GetPtr()
    );
    const auto compoundTransform = JPH::Mat44::sRotationTranslation(
        JPH::Quat::sRotation(JPH::Vec3::sAxisY(),
                             std::numbers::pi_v<float> / 2.0f),
        JPH::Vec3::sZero()
    );
    const auto probeTransform = JPH::Mat44::sTranslation(
        JPH::Vec3(0.0f, 0.0f, -3.25f)
    );
    JPH::CollideShapeSettings collisionSettings;
    collisionSettings.mMaxSeparationDistance = 2.0f;
    JPH::ClosestHitCollisionCollector<JPH::CollideShapeCollector> collector;
    JPH::CollisionDispatch::sCollideShapeVsShape(
        sphere.GetPtr(), compound, JPH::Vec3::sOne(), JPH::Vec3::sOne(),
        probeTransform, compoundTransform, JPH::SubShapeIDCreator(),
        JPH::SubShapeIDCreator(), collisionSettings, collector
    );
    if (!collector.HadHit()) return 4;
    JPH::SubShapeID collisionRemainder;
    const auto collisionIndex = compound->GetSubShapeIndexFromID(
        collector.mHit.mSubShapeID2, collisionRemainder
    );

    const JPH::RayCast worldRay(
        JPH::Vec3(0.0f, 0.0f, -5.0f), JPH::Vec3(0.0f, 0.0f, 5.0f)
    );
    const auto localRay = worldRay.Transformed(
        compoundTransform.InversedRotationTranslation()
    );
    JPH::RayCastResult rayHit;
    if (!compound->CastRay(localRay, JPH::SubShapeIDCreator(), rayHit)) return 5;
    JPH::SubShapeID rayRemainder;
    const auto rayIndex = compound->GetSubShapeIndexFromID(
        rayHit.mSubShapeID2, rayRemainder
    );

    std::cout.precision(9);
    std::cout << "separation=" << -collector.mHit.mPenetrationDepth << '\n'
              << "collision_child=" << compound->GetSubShape(collisionIndex).mUserData << '\n'
              << "ray_fraction=" << rayHit.mFraction << '\n'
              << "ray_child=" << compound->GetSubShape(rayIndex).mUserData << '\n';

    return 0;
}

int run() {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();
    const auto result = run_case();
    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return result;
}

} // namespace Physics3D

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n';
        return 0;
    }
    if (count != 1) return 2;
    return Physics3D::run();
}
