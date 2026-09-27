#include <Jolt/Jolt.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/CollisionDispatch.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <array>
#include <charconv>
#include <iostream>
#include <numbers>
#include <string_view>

namespace Physics3D {

// -----------------------------------------------------------------------------

struct Fixture {
    std::string_view first;
    std::string_view second;
    std::array<int, 8> scalars;
};

bool parseFixture(int count, char** values, Fixture& fixture) {
    if (count != 11) return false;
    fixture.first = values[1];
    fixture.second = values[2];
    if ((fixture.first != "sphere" && fixture.first != "box") ||
        (fixture.second != "sphere" && fixture.second != "box")) return false;
    for (std::size_t index = 0; index < fixture.scalars.size(); ++index) {
        const char* text = values[index + 3];
        const char* end = text + std::char_traits<char>::length(text);
        const auto result = std::from_chars(text, end, fixture.scalars[index]);
        if (result.ec != std::errc{} || result.ptr != end) return false;
    }
    return fixture.scalars[2] >= 0 && fixture.scalars[2] <= 360 &&
        (fixture.scalars[3] != 0 || fixture.scalars[4] != 0 ||
         fixture.scalars[5] != 0) && fixture.scalars[7] > 0;
}

void printVector(std::string_view name, JPH::Vec3Arg vector) {
    std::cout << name << "_x=" << vector.GetX() << '\n'
              << name << "_y=" << vector.GetY() << '\n'
              << name << "_z=" << vector.GetZ() << '\n';
}

int run(const Fixture& fixture) {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();

    JPH::SphereShape sphere(1.0f);
    JPH::BoxShape box(JPH::Vec3::sOne(), 0.0f);
    const JPH::Shape* first = fixture.first == "sphere" ?
        static_cast<const JPH::Shape*>(&sphere) : static_cast<const JPH::Shape*>(&box);
    const JPH::Shape* second = fixture.second == "sphere" ?
        static_cast<const JPH::Shape*>(&sphere) : static_cast<const JPH::Shape*>(&box);
    const auto firstX = static_cast<float>(fixture.scalars[0]) / 1000.0f;
    const auto secondX = static_cast<float>(fixture.scalars[1]) / 1000.0f;
    const auto angle = static_cast<float>(fixture.scalars[2]) *
        std::numbers::pi_v<float> / 180.0f;
    const auto axis = JPH::Vec3(
        fixture.scalars[3], fixture.scalars[4], fixture.scalars[5]
    ).Normalized();
    const auto firstTransform = JPH::Mat44::sTranslation(JPH::Vec3(firstX, 0, 0));
    const auto secondTransform = JPH::Mat44::sRotationTranslation(
        JPH::Quat::sRotation(axis, angle),
        JPH::Vec3(secondX, 0, 0)
    );
    JPH::CollideShapeSettings settings;
    settings.mMaxSeparationDistance = 10.0f;
    JPH::ClosestHitCollisionCollector<JPH::CollideShapeCollector> collector;
    JPH::CollisionDispatch::sCollideShapeVsShape(
        first, second, JPH::Vec3::sOne(), JPH::Vec3::sOne(),
        firstTransform, secondTransform, JPH::SubShapeIDCreator(),
        JPH::SubShapeIDCreator(), settings, collector
    );
    if (!collector.HadHit()) return 3;
    const auto& hit = collector.mHit;

    const JPH::RayCast worldRay(
        JPH::Vec3(static_cast<float>(fixture.scalars[6]) / 1000.0f, 0, 0),
        JPH::Vec3(static_cast<float>(fixture.scalars[7]) / 1000.0f, 0, 0)
    );
    const auto localRay = worldRay.Transformed(
        secondTransform.InversedRotationTranslation()
    );
    JPH::RayCastResult rayHit;
    if (!second->CastRay(localRay, JPH::SubShapeIDCreator(), rayHit)) return 4;

    std::cout.precision(9);
    std::cout << "separation=" << -hit.mPenetrationDepth << '\n';
    printVector("first_point", hit.mContactPointOn1);
    printVector("second_point", hit.mContactPointOn2);
    printVector("normal", hit.mPenetrationAxis.Normalized());
    std::cout << "ray_fraction=" << rayHit.mFraction << '\n';

    JPH::UnregisterTypes();
    delete JPH::Factory::sInstance;
    JPH::Factory::sInstance = nullptr;
    return 0;
}

} // namespace Physics3D

int main(int count, char** values) {
    Physics3D::Fixture fixture {};
    if (!Physics3D::parseFixture(count, values, fixture)) {
        std::cerr << "invalid physics3d geometry fixture arguments\n";
        return 2;
    }
    return Physics3D::run(fixture);
}
