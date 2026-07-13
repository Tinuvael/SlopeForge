import numpy as np
import pandas as pd
import trimesh

print("Loading files...")

# --------------------------------
# Треугольники Datamine
# PID,X,Y,Z,FID
# --------------------------------
tri = pd.read_csv("basetr.csv")

# --------------------------------
# Точки съемки
# X,Y,Z
# --------------------------------
survey = pd.read_csv("points.csv")

print(f"Triangle rows : {len(tri)}")
print(f"Survey points : {len(survey)}")

# --------------------------------
# Создаем mesh
# --------------------------------

vertices = []
faces = []

for fid, group in tri.groupby("FID"):

    if len(group) != 3:
        continue

    start = len(vertices)

    for _, row in group.iterrows():
        vertices.append([
            row["X"],
            row["Y"],
            row["Z"]
        ])

    faces.append([
        start,
        start + 1,
        start + 2
    ])

vertices = np.array(vertices)
faces = np.array(faces)

print(f"Vertices : {len(vertices)}")
print(f"Faces    : {len(faces)}")

mesh = trimesh.Trimesh(
    vertices=vertices,
    faces=faces,
    process=False
)

# --------------------------------
# Точки съемки
# --------------------------------

points = survey[["X", "Y", "Z"]].to_numpy()

print("Searching nearest surface...")

closest, dist, tri_id = mesh.nearest.on_surface(points)

print("Done!")

# --------------------------------
# Статистика
# --------------------------------

rms = np.sqrt(np.mean(dist ** 2))

print("------------------------")
print(f"RMS  : {rms:.3f} m")
print(f"Mean : {dist.mean():.3f} m")
print(f"Std  : {dist.std():.3f} m")
print(f"Max  : {dist.max():.3f} m")
print(f"Min  : {dist.min():.3f} m")
print("------------------------")

# --------------------------------
# Сохраняем
# --------------------------------

survey["DIST"] = dist

survey.to_csv(
    "distance.csv",
    index=False
)

print("distance.csv saved")
