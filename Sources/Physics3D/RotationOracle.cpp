#include <Jolt/Jolt.h>
#include <Jolt/ConfigurationString.h>
#include <array>
#include <cmath>
#include <iostream>
#include <string_view>
#include <Jolt/Core/Factory.h>
#include <Jolt/RegisterTypes.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/ContactListener.h>
#include <Jolt/Physics/Collision/BroadPhase/BroadPhaseLayerInterfaceTable.h>
#include <Jolt/Physics/Collision/BroadPhase/ObjectVsBroadPhaseLayerFilterTable.h>
#include <Jolt/Physics/Collision/ObjectLayerPairFilterTable.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>

namespace Physics3D {
class ContactCount final : public JPH::ContactListener {
    public: void OnContactAdded(const JPH::Body&, const JPH::Body&, const JPH::ContactManifold&, JPH::ContactSettings&) override { ++addedCount; }
    public: [[nodiscard]] int added() const { return addedCount; }
    private: int addedCount = 0;
};

//------------------------------------------------------------------------------

void runCase(bool translating, int subdivisions) {
    JPH::BroadPhaseLayerInterfaceTable broadPhase(1, 1);
    broadPhase.MapObjectToBroadPhaseLayer(0, JPH::BroadPhaseLayer(0));
    JPH::ObjectLayerPairFilterTable pairFilter(1); pairFilter.EnableCollision(0, 0);
    JPH::ObjectVsBroadPhaseLayerFilterTable phaseFilter(broadPhase, 1, pairFilter, 1);
    JPH::PhysicsSystem world; world.Init(16, 0, 32, 32, broadPhase, phaseFilter, pairFilter);
    world.SetGravity(JPH::Vec3::sZero());
    ContactCount contacts; world.SetContactListener(&contacts);
    JPH::BoxShapeSettings bladeSettings(JPH::Vec3(0.05f, 1.0f, 0.05f), 0.0f); bladeSettings.mDensity = 1.0f;
    const auto blade = bladeSettings.Create();
    const auto wall = JPH::BoxShapeSettings(JPH::Vec3(0.05f, 2.0f, 2.0f), 0.0f).Create();
    JPH::BodyCreationSettings fixedSettings(wall.Get(), JPH::RVec3::sZero(), JPH::Quat::sIdentity(), JPH::EMotionType::Static, 0);
    fixedSettings.mFriction = 0.0f;
    JPH::BodyCreationSettings bodySettings(blade.Get(), JPH::RVec3(-0.4f, 0.0f, 0.0f), JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, 0);
    bodySettings.mAllowSleeping = false; bodySettings.mLinearDamping = 0.0f; bodySettings.mAngularDamping = 0.0f; bodySettings.mFriction = 0.0f;
    bodySettings.mMotionQuality = JPH::EMotionQuality::LinearCast;
    bodySettings.mMaxAngularVelocity = 1000.0f;
    bodySettings.mAngularVelocity = JPH::Vec3(0.0f, 0.0f, JPH::JPH_PI * 60.0f);
    bodySettings.mLinearVelocity = JPH::Vec3(0.0f, 0.0f, translating ? 120.0f : 0.0f);
    auto& bodies = world.GetBodyInterface();
    const auto fixed = bodies.CreateAndAddBody(fixedSettings, JPH::EActivation::DontActivate);
    const auto moving = bodies.CreateAndAddBody(bodySettings, JPH::EActivation::Activate);
    JPH::TempAllocatorImpl allocator(1024 * 1024); JPH::JobSystemSingleThreaded jobs(128);
    for (int step = 0; step < subdivisions; ++step) {
        world.Update(1.0f / (60.0f * static_cast<float>(subdivisions)), 1, &allocator, &jobs);
    }
    const auto position = bodies.GetPosition(moving);
    const auto axis = bodies.GetRotation(moving) * JPH::Vec3::sAxisY();
    std::cout << "rotation translating=" << translating << " subdivisions=" << subdivisions << " contacts=" << contacts.added()
        << " x=" << position.GetX() << " z=" << position.GetZ() << " axis_y=" << axis.GetY() << '\n';
    bodies.RemoveBody(moving); bodies.DestroyBody(moving); bodies.RemoveBody(fixed); bodies.DestroyBody(fixed);
    world.SetContactListener(nullptr);
}
} // namespace Physics3D

//------------------------------------------------------------------------------

int main(int argc, char* argv[]) {
    if (argc == 2 && std::string_view(argv[1]) == "--configuration") {
        std::cout << JPH::GetConfigurationString() << '\n'; return 0;
    }
    if (argc != 1) { return 2; }
    JPH::RegisterDefaultAllocator(); JPH::Factory factory; JPH::Factory::sInstance = &factory; JPH::RegisterTypes();
    std::cout.precision(9);
    for (const bool translating : std::array{false, true}) {
        for (const int subdivisions : std::array{1, 36}) { Physics3D::runCase(translating, subdivisions); }
    }
    JPH::UnregisterTypes(); JPH::Factory::sInstance = nullptr;
}
