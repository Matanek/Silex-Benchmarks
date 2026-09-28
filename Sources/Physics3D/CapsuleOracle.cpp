#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/CollisionDispatch.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <charconv>
#include <iostream>
#include <numbers>
#include <string_view>

namespace Physics3D {

int run(int centerMillimeters) {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();

    JPH::CapsuleShape capsule(0.5f, 0.25f);
    JPH::BoxShape box(JPH::Vec3::sOne(), 0.0f);
    const auto angle = std::numbers::pi_v<float> / 6.0f;
    const auto capsuleTransform = JPH::Mat44::sRotationTranslation(
        JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), angle),
        JPH::Vec3(centerMillimeters / 1000.0f, 0.0f, 0.0f)
    );
    JPH::CollideShapeSettings settings;
    settings.mMaxSeparationDistance = 1.0f;
    JPH::ClosestHitCollisionCollector<JPH::CollideShapeCollector> collector;
    JPH::CollisionDispatch::sCollideShapeVsShape(
        &capsule, &box, JPH::Vec3::sOne(), JPH::Vec3::sOne(),
        capsuleTransform, JPH::Mat44::sIdentity(),
        JPH::SubShapeIDCreator(), JPH::SubShapeIDCreator(), settings, collector
    );
    if (!collector.HadHit()) return 3;
    const auto& hit = collector.mHit;
    std::cout.precision(9);
    std::cout << "separation=" << -hit.mPenetrationDepth << '\n'
              << "first_x=" << hit.mContactPointOn1.GetX() << '\n'
              << "first_y=" << hit.mContactPointOn1.GetY() << '\n'
              << "second_x=" << hit.mContactPointOn2.GetX() << '\n'
              << "second_y=" << hit.mContactPointOn2.GetY() << '\n'
              << "normal_x=" << hit.mPenetrationAxis.Normalized().GetX() << '\n';

    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return 0;
}

} // namespace Physics3D

int main(int count, char** values) {
    if (count == 2 && std::string_view(values[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n';
        return 0;
    }
    if (count != 2) return 2;
    auto center = 0;
    const auto* end = values[1] + std::char_traits<char>::length(values[1]);
    const auto parsed = std::from_chars(values[1], end, center);
    if (parsed.ec != std::errc{} || parsed.ptr != end || center < 1000 || center > 2000) {
        return 2;
    }
    return Physics3D::run(center);
}
