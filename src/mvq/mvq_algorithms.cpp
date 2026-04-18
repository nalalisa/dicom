#include "mvq/mvq_engine.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace mvq {

namespace {

Vec3d Add(const Vec3d& a, const Vec3d& b) {
  return {a.x + b.x, a.y + b.y, a.z + b.z};
}

Vec3d Sub(const Vec3d& a, const Vec3d& b) {
  return {a.x - b.x, a.y - b.y, a.z - b.z};
}

Vec3d Scale(const Vec3d& a, double s) {
  return {a.x * s, a.y * s, a.z * s};
}

double Dot(const Vec3d& a, const Vec3d& b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

Vec3d Cross(const Vec3d& a, const Vec3d& b) {
  return {
      a.y * b.z - a.z * b.y,
      a.z * b.x - a.x * b.z,
      a.x * b.y - a.y * b.x,
  };
}

double Norm(const Vec3d& a) {
  return std::sqrt(Dot(a, a));
}

Vec3d Normalize(const Vec3d& a) {
  const double n = Norm(a);
  if (n <= 1e-12) {
    return {0.0, 0.0, 0.0};
  }
  return Scale(a, 1.0 / n);
}

double Clamp(double v, double lo, double hi) {
  return std::max(lo, std::min(v, hi));
}

const std::vector<Vec3d>& GetAnnulusSamples(const AnnulusModel& annulus) {
  if (!annulus.sampled_curve.points.empty()) {
    return annulus.sampled_curve.points;
  }
  return annulus.spline.control_points;
}

double MinDistanceToPointCloud(const Vec3d& point, const PointCloud3d& cloud) {
  if (cloud.points.empty()) {
    return std::numeric_limits<double>::infinity();
  }

  double best = std::numeric_limits<double>::infinity();
  for (const Vec3d& candidate : cloud.points) {
    best = std::min(best, geometry::ComputeDistance(point, candidate));
  }
  return best;
}

double ScoreDistance(double distance_mm, double sigma_mm) {
  if (!std::isfinite(distance_mm)) {
    return 0.0;
  }
  const double x = distance_mm / std::max(1e-6, sigma_mm);
  return std::exp(-0.5 * x * x);
}

std::pair<std::size_t, std::size_t> ExpandAnteriorArc(
    const std::vector<double>& scores,
    std::size_t peak_index,
    double relative_threshold) {
  const std::size_t n = scores.size();
  if (n == 0) {
    return {0, 0};
  }

  const double threshold = scores[peak_index] * relative_threshold;
  std::size_t left = peak_index;
  std::size_t right = peak_index;

  while (true) {
    const std::size_t next = (left + n - 1) % n;
    if (next == right || scores[next] < threshold) {
      break;
    }
    left = next;
  }

  while (true) {
    const std::size_t next = (right + 1) % n;
    if (next == left || scores[next] < threshold) {
      break;
    }
    right = next;
  }

  return {left, right};
}

Polyline3d BuildArc(const std::vector<Vec3d>& points,
                    std::size_t start,
                    std::size_t end) {
  Polyline3d line;
  if (points.empty()) {
    return line;
  }

  const std::size_t n = points.size();
  std::size_t idx = start;
  while (true) {
    line.points.push_back(points[idx]);
    if (idx == end) {
      break;
    }
    idx = (idx + 1) % n;
  }
  line.closed = false;
  return line;
}

double SafeProjection(const Vec3d& point,
                      const Vec3d& origin,
                      const Vec3d& axis) {
  const Vec3d u = Normalize(axis);
  return Dot(Sub(point, origin), u);
}

}  // namespace

namespace geometry {

double ComputePolylineLength(const Polyline3d& line) {
  double length = 0.0;
  for (std::size_t i = 1; i < line.points.size(); ++i) {
    length += ComputeDistance(line.points[i - 1], line.points[i]);
  }
  if (line.closed && line.points.size() > 2) {
    length += ComputeDistance(line.points.back(), line.points.front());
  }
  return length;
}

double ComputePointToPlaneSignedDistance(const Vec3d& point, const Plane3d& plane) {
  const Vec3d n = Normalize(plane.normal);
  return Dot(Sub(point, plane.origin), n);
}

Vec3d ComputeCentroid(const std::vector<Vec3d>& points) {
  if (points.empty()) {
    return {};
  }

  Vec3d sum;
  for (const Vec3d& p : points) {
    sum = Add(sum, p);
  }
  return Scale(sum, 1.0 / static_cast<double>(points.size()));
}

double ComputeTriangleArea(const Vec3d& a, const Vec3d& b, const Vec3d& c) {
  return 0.5 * Norm(Cross(Sub(b, a), Sub(c, a)));
}

double ComputeMeshArea(const SurfaceMesh& mesh) {
  double area = 0.0;
  for (const Triangle& tri : mesh.faces) {
    const Vec3d& a = mesh.vertices[tri.indices[0]];
    const Vec3d& b = mesh.vertices[tri.indices[1]];
    const Vec3d& c = mesh.vertices[tri.indices[2]];
    area += ComputeTriangleArea(a, b, c);
  }
  return area;
}

double ComputeDistance(const Vec3d& a, const Vec3d& b) {
  return Norm(Sub(a, b));
}

double ComputeAngleDegrees(const Vec3d& a, const Vec3d& b) {
  const Vec3d ua = Normalize(a);
  const Vec3d ub = Normalize(b);
  const double d = Clamp(Dot(ua, ub), -1.0, 1.0);
  return std::acos(d) * 180.0 / 3.14159265358979323846;
}

Vec3d ProjectPointToPlane(const Vec3d& point, const Plane3d& plane) {
  const double d = ComputePointToPlaneSignedDistance(point, plane);
  return Sub(point, Scale(Normalize(plane.normal), d));
}

}  // namespace geometry

TrigoneExtractionResult RuleBasedTrigoneExtractor::Extract(
    const TensorDerivedData& tensor_data,
    const AnnulusModel& annulus,
    const AorticModel& aortic,
    const LandmarkSet& seed_landmarks,
    const ReconstructionOptions& options) const {
  (void)options;

  const std::vector<Vec3d>& annulus_points = GetAnnulusSamples(annulus);
  if (annulus_points.size() < 8) {
    throw std::runtime_error("RuleBasedTrigoneExtractor requires a sampled annulus curve.");
  }

  const auto aortic_it = tensor_data.point_clouds.find(LabelClass::kAorticValve);
  const auto aml_it = tensor_data.point_clouds.find(LabelClass::kAnteriorLeaflet);
  const auto pml_it = tensor_data.point_clouds.find(LabelClass::kPosteriorLeaflet);

  const PointCloud3d empty_cloud;
  const PointCloud3d& aortic_cloud = (aortic_it != tensor_data.point_clouds.end()) ? aortic_it->second : empty_cloud;
  const PointCloud3d& aml_cloud = (aml_it != tensor_data.point_clouds.end()) ? aml_it->second : empty_cloud;
  const PointCloud3d& pml_cloud = (pml_it != tensor_data.point_clouds.end()) ? pml_it->second : empty_cloud;

  // Score annular samples along the anterior fibrous curtain.
  // High score if:
  // 1) near the aortic model/cloud,
  // 2) on the high anterior saddle of the annulus,
  // 3) closer to AML than PML,
  // 4) aligned with the aorto-mitral continuity.
  std::vector<double> scores(annulus_points.size(), 0.0);

  for (std::size_t i = 0; i < annulus_points.size(); ++i) {
    const Vec3d& p = annulus_points[i];

    const double d_aortic_plane = std::abs(geometry::ComputePointToPlaneSignedDistance(p, aortic.annulus_plane));
    const double d_aortic_cloud = MinDistanceToPointCloud(p, aortic_cloud);
    const double d_aml = MinDistanceToPointCloud(p, aml_cloud);
    const double d_pml = MinDistanceToPointCloud(p, pml_cloud);
    const double annulus_height = geometry::ComputePointToPlaneSignedDistance(p, annulus.best_fit_plane);

    const double aortic_plane_score = ScoreDistance(d_aortic_plane, 3.0);
    const double aortic_cloud_score = ScoreDistance(d_aortic_cloud, 4.0);
    const double aml_bias = ScoreDistance(d_aml, 6.0);
    const double pml_penalty = ScoreDistance(d_pml, 6.0);
    const double height_score = Clamp((annulus_height + 4.0) / 8.0, 0.0, 1.0);

    // Reward AML continuity and penalize strong posterior support.
    const double fibrous_continuity_score =
        0.35 * aortic_plane_score +
        0.30 * aortic_cloud_score +
        0.25 * height_score +
        0.20 * aml_bias -
        0.15 * pml_penalty;

    scores[i] = std::max(0.0, fibrous_continuity_score);
  }

  const auto peak_it = std::max_element(scores.begin(), scores.end());
  const std::size_t peak_index = static_cast<std::size_t>(std::distance(scores.begin(), peak_it));
  const auto [left_index, right_index] = ExpandAnteriorArc(scores, peak_index, 0.70);

  Polyline3d anterior_arc = BuildArc(annulus_points, left_index, right_index);
  Vec3d left_trigone = annulus_points[left_index];
  Vec3d right_trigone = annulus_points[right_index];

  // Orient left/right consistently with the commissural axis.
  if (SafeProjection(left_trigone, annulus.best_fit_plane.origin, annulus.commissural_axis.direction) >
      SafeProjection(right_trigone, annulus.best_fit_plane.origin, annulus.commissural_axis.direction)) {
    std::swap(left_trigone, right_trigone);
  }

  // If a seed trigone exists, use it as a weak refinement anchor by snapping to the
  // nearest endpoint when the candidate is already close enough.
  auto refine_from_seed = [&](LandmarkId id, Vec3d& point) {
    const auto it = seed_landmarks.points.find(id);
    if (it == seed_landmarks.points.end()) {
      return;
    }
    if (geometry::ComputeDistance(it->second.position, point) < 6.0) {
      point = it->second.position;
    }
  };
  refine_from_seed(LandmarkId::kLeftTrigone, left_trigone);
  refine_from_seed(LandmarkId::kRightTrigone, right_trigone);

  TrigoneExtractionResult result;
  result.left_trigone = {LandmarkId::kLeftTrigone, left_trigone, scores[left_index], "rule_based_aorto_mitral_continuity"};
  result.right_trigone = {LandmarkId::kRightTrigone, right_trigone, scores[right_index], "rule_based_aorto_mitral_continuity"};
  result.anterior_fibrous_arc = std::move(anterior_arc);
  result.continuity_score = *peak_it;
  return result;
}

}  // namespace mvq
