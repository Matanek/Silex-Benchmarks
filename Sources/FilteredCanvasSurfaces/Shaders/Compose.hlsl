Texture2D<float4> canvasTexture : register(t0, space2);
SamplerState canvasSampler : register(s0, space2);

struct VertexOutput {
    float2 uv : TEXCOORD0;
    float4 position : SV_Position;
};

VertexOutput vertex_main(uint id : SV_VertexID) {
    const float2 positions[3] = {
        float2(-1.0, -1.0),
        float2(3.0, -1.0),
        float2(-1.0, 3.0)
    };
    VertexOutput output;
    output.position = float4(positions[id], 0.0, 1.0);
    output.uv = float2(
        positions[id].x * 0.5 + 0.5,
        0.5 - positions[id].y * 0.5
    );
    return output;
}

float4 fragment_main(VertexOutput input) : SV_Target0 {
    return canvasTexture.Sample(canvasSampler, input.uv);
}
