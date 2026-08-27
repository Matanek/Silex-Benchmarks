#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <numbers>
#include <random>
#include <span>
#include <vector>

#include <SDL3/SDL.h>

namespace {

// -----------------------------------------------------------------------------

constexpr float k_neighborhoodRadius = 72.0F;
constexpr float k_separationRadius = 28.0F;
constexpr float k_minimumSpeed = 55.0F;
constexpr float k_maximumSpeed = 105.0F;
constexpr float k_maximumSteering = 140.0F;
constexpr float k_halfWidth = 490.0F;
constexpr float k_halfHeight = 330.0F;
constexpr int k_windowWidth = 960;
constexpr int k_windowHeight = 640;
constexpr float k_neighborhoodRadiusSquared =
    k_neighborhoodRadius * k_neighborhoodRadius;
constexpr float k_separationRadiusSquared =
    k_separationRadius * k_separationRadius;

struct Vector2 {
    float x { 0.0F };
    float y { 0.0F };
};

struct Boid {
    Vector2 position;
    Vector2 velocity;
};

// -----------------------------------------------------------------------------

Vector2 operator+(Vector2 lhs, Vector2 rhs) {
    return { lhs.x + rhs.x, lhs.y + rhs.y };
}

Vector2 operator-(Vector2 lhs, Vector2 rhs) {
    return { lhs.x - rhs.x, lhs.y - rhs.y };
}

Vector2 operator*(Vector2 value, float scalar) {
    return { value.x * scalar, value.y * scalar };
}

Vector2 operator/(Vector2 value, float scalar) {
    return { value.x / scalar, value.y / scalar };
}

float lengthSquared(Vector2 value) {
    return value.x * value.x + value.y * value.y;
}

float length(Vector2 value) {
    return std::sqrt(lengthSquared(value));
}

Vector2 limit(Vector2 value, float maximum) {
    const float currentLength = length(value);
    return currentLength > maximum ? value * (maximum / currentLength) : value;
}

Vector2 keepSpeed(Vector2 value) {
    const float speed = length(value);
    if (speed > k_maximumSpeed) return value * (k_maximumSpeed / speed);
    if (speed < k_minimumSpeed && speed > 0.0F) {
        return value * (k_minimumSpeed / speed);
    }
    return value;
}

Vector2 wrap(Vector2 position) {
    if (position.x < -k_halfWidth) {
        position.x = k_halfWidth;
    } else if (position.x > k_halfWidth) {
        position.x = -k_halfWidth;
    }
    if (position.y < -k_halfHeight) {
        position.y = k_halfHeight;
    } else if (position.y > k_halfHeight) {
        position.y = -k_halfHeight;
    }
    return position;
}

// -----------------------------------------------------------------------------

Vector2 steering(const Boid& boid, std::span<const Boid> snapshot) {
    Vector2 separation;
    Vector2 center;
    Vector2 heading;
    int neighbors = 0;
    for (const Boid& other : snapshot) {
        const Vector2 offset = boid.position - other.position;
        const float distanceSquared = lengthSquared(offset);
        if (distanceSquared > 0.0F
            && distanceSquared < k_neighborhoodRadiusSquared) {
            center = center + other.position;
            heading = heading + other.velocity;
            ++neighbors;
            if (distanceSquared < k_separationRadiusSquared) {
                separation = separation + offset / std::max(distanceSquared, 1.0F);
            }
        }
    }
    if (neighbors == 0) return {};
    const float count = static_cast<float>(neighbors);
    const Vector2 cohesion = (center / count - boid.position) * 0.35F;
    const Vector2 alignment = (heading / count - boid.velocity) * 0.8F;
    return limit(
        cohesion + alignment + separation * 1400.0F,
        k_maximumSteering
    );
}

void renderBoid(SDL_Renderer* renderer, const Boid& boid, int index) {
    const float angle = std::atan2(boid.velocity.y, boid.velocity.x);
    const float cosine = std::cos(angle);
    const float sine = std::sin(angle);
    constexpr std::array<Vector2, 3> k_shape {
        { { 8.0F, 0.0F }, { -7.0F, 6.0F }, { -7.0F, -6.0F } }
    };
    constexpr std::array<SDL_FColor, 3> k_colors {{
        { 0.49F, 0.83F, 0.99F, 1.0F },
        { 0.13F, 0.83F, 0.93F, 1.0F },
        { 0.51F, 0.55F, 0.97F, 1.0F }
    }};
    std::array<SDL_Vertex, 3> vertices {};
    for (std::size_t vertex = 0; vertex < vertices.size(); ++vertex) {
        const Vector2 point = k_shape[vertex];
        vertices[vertex].position = {
            static_cast<float>(k_windowWidth) * 0.5F + boid.position.x
                + point.x * cosine - point.y * sine,
            static_cast<float>(k_windowHeight) * 0.5F + boid.position.y
                + point.x * sine + point.y * cosine
        };
        vertices[vertex].color = k_colors[static_cast<std::size_t>(index % 3)];
    }
    SDL_RenderGeometry(
        renderer,
        nullptr,
        vertices.data(),
        static_cast<int>(vertices.size()),
        nullptr,
        0
    );
}

int parseCount(const char* text) {
    int value = 100;
    const auto result = std::from_chars(
        text,
        text + std::char_traits<char>::length(text),
        value
    );
    return result.ec == std::errc {} && value > 0 ? value : 100;
}

// -----------------------------------------------------------------------------

} // namespace

int main(int argc, char** argv) {
    const int count = argc > 1 ? parseCount(argv[1]) : 100;
    if (!SDL_Init(SDL_INIT_VIDEO)) return EXIT_FAILURE;

    SDL_Window* window = nullptr;
    SDL_Renderer* renderer = nullptr;
    if (!SDL_CreateWindowAndRenderer(
        "C++ Direct SDL Boids",
        k_windowWidth,
        k_windowHeight,
        SDL_WINDOW_HIGH_PIXEL_DENSITY,
        &window,
        &renderer
    )) {
        SDL_Quit();
        return EXIT_FAILURE;
    }
    if (!SDL_SetRenderVSync(renderer, SDL_RENDERER_VSYNC_DISABLED)
        || !SDL_SetRenderLogicalPresentation(
            renderer,
            k_windowWidth,
            k_windowHeight,
            SDL_LOGICAL_PRESENTATION_STRETCH
        )) {
        std::fprintf(
            stderr,
            "Could not configure immediate high-density rendering: %s\n",
            SDL_GetError()
        );
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return EXIT_FAILURE;
    }

    int windowWidth = 0;
    int windowHeight = 0;
    int pixelWidth = 0;
    int pixelHeight = 0;
    if (!SDL_GetWindowSize(window, &windowWidth, &windowHeight)
        || !SDL_GetWindowSizeInPixels(window, &pixelWidth, &pixelHeight)) {
        std::fprintf(
            stderr,
            "Could not query benchmark window dimensions: %s\n",
            SDL_GetError()
        );
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return EXIT_FAILURE;
    }
    const float displayScale = SDL_GetWindowDisplayScale(window);
    const float pixelDensity = SDL_GetWindowPixelDensity(window);

    std::mt19937 randomizer { 0x511E801D };
    std::uniform_real_distribution<float> xPosition { -k_halfWidth, k_halfWidth };
    std::uniform_real_distribution<float> yPosition { -k_halfHeight, k_halfHeight };
    std::uniform_real_distribution<float> angleDistribution {
        0.0F,
        2.0F * std::numbers::pi_v<float>
    };
    std::uniform_real_distribution<float> speedDistribution {
        k_minimumSpeed,
        k_maximumSpeed
    };
    std::vector<Boid> boids;
    boids.reserve(static_cast<std::size_t>(count));
    for (int index = 0; index < count; ++index) {
        const float angle = angleDistribution(randomizer);
        const float speed = speedDistribution(randomizer);
        boids.push_back({
            { xPosition(randomizer), yPosition(randomizer) },
            { std::cos(angle) * speed, std::sin(angle) * speed }
        });
    }

    using Clock = std::chrono::steady_clock;
    auto previous = Clock::now();
    const auto start = previous;
    int frames = 0;
    while (std::chrono::duration<float>(Clock::now() - start).count() < 5.0F) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {}

        const auto now = Clock::now();
        const float delta = std::chrono::duration<float>(now - previous).count();
        previous = now;
        const std::vector<Boid> snapshot = boids;
        for (Boid& boid : boids) {
            boid.velocity = keepSpeed(
                boid.velocity + steering(boid, snapshot) * delta
            );
            boid.position = wrap(boid.position + boid.velocity * delta);
        }

        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
        SDL_RenderClear(renderer);
        for (int index = 0; index < count; ++index) {
            renderBoid(renderer, boids[static_cast<std::size_t>(index)], index);
        }
        SDL_RenderPresent(renderer);
        ++frames;
    }

    const float seconds = std::chrono::duration<float>(Clock::now() - start).count();
    std::printf(
        "CPP_DIRECT_BOIDS count=%d present=immediate fps=%.5f "
        "window=%dx%d pixels=%dx%d scale=%.5f density=%.5f\n",
        count,
        static_cast<double>(frames) / seconds,
        windowWidth,
        windowHeight,
        pixelWidth,
        pixelHeight,
        static_cast<double>(displayScale),
        static_cast<double>(pixelDensity)
    );

    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
}
