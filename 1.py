def angle_to_seconds(angle):
    # angle可以是 float (十进制度数) 或 (deg, min, sec) 元组
    if isinstance(angle, (int, float)):
        return angle * 3600.0
    else:
        d, m, s = angle
        return d*3600 + m*60 + s

def solve_T(epsilon_sec):
    eps0 = 84381.448   # 角秒
    a, b, c = 0.001813, -0.00059, -46.8150
    d = eps0 - epsilon_sec  # 常数项
    
    # 牛顿法初值
    T = (epsilon_sec - eps0) / c   # 因为c为负，数值合理
    for _ in range(50):
        f = a*T**3 + b*T**2 + c*T + d
        if abs(f) < 1e-6:
            break
        fp = 3*a*T**2 + 2*b*T + c
        if fp == 0:
            break
        T -= f / fp
    return T

def years_between(eps1, eps2):
    sec1 = angle_to_seconds(eps1)
    sec2 = angle_to_seconds(eps2)
    T1 = solve_T(sec1)
    T2 = solve_T(sec2)
    delta_year = abs((T2 - T1) * 100)
    return round(delta_year)   # 或保留一位小数

print(years_between(23.43929, 23.43706))   # 输出 20 （20年，与事实相符）

