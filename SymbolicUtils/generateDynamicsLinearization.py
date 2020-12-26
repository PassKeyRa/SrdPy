from casadi import *
from SrdPy import SymbolicEngine
import os

def generateDynamicsLinearization(symbolicEngine:SymbolicEngine,
                                    H, c, T,
                                    functionName_A,
                                    functionName_B,
                                    functionName_c,
                                    casadi_cCodeFilename,
                                    path):

    # H*ddq + c = T*u;        ddq = dv/dt; v = dq/dt;
    # x = [q; v]
    #
    #
    # f= ddq = inv(H) * (T*u - c)
    #
    # dx/dt = A*x+B*u+lc
    #
    # A = [0      I]
    #     [df/dq  df/dv  ]
    #
    # B = [0           ]
    #     [inv(H)*T    ]
    #
    # lc = [0                             ]
    #      [inv(H)*c - df/dq*q -  df/dv*v ]
    #
    # df / dq = d(inv(H))/dq * (T*u - c) + d(T*u - c)/dq
    # df / dq = inv(H) * dH/dq * inv(H) * (T*u - c) + d(T*u - c)/dq
    #
    # df / dv = inv(H)* d(T*u - c)/dv


    q = symbolicEngine.q
    v = symbolicEngine.v
    u = symbolicEngine.u

    n = symbolicEngine.dof
    m = symbolicEngine.u.shape[0]

    iH = SX.sym('iH', n, n)

    TCq = jacobian(T@u+c, q)
    TCv = jacobian(T@u+c, v)



    dfdq = -iH@reshape(jacobian(H, q)@(iH@(T@u+c)), n, n) + TCq

    dfdv = iH @ TCv

    A1 = vertcat(SX.zeros(n, n),SX.eye(n))
    A2 = vertcat(dfdq.T,dfdv.T)
    A = horzcat(A1,A2)

    B = horzcat(SX.zeros(n, m),iH@T)

    linear_c = horzcat(SX.zeros(n, 1),iH@c - dfdq@q - dfdv@v)

    print('Starting writing function for the '+functionName_A)
    g_linearization_A = Function(functionName_A,
                                 [symbolicEngine.q,symbolicEngine.v,symbolicEngine.u,iH], [A],
                                 ['q', 'v', 'u', 'iH'], ['A'])

    print('Starting writing function for the ' + functionName_B)
    g_linearization_B = Function(functionName_B,
                                 [symbolicEngine.q,symbolicEngine.v,iH], [B],
                                 ['q', 'v', 'iH'], ['B'])

    print('Starting writing function for the ' + functionName_c)
    g_linearization_c = Function(functionName_c,
                                     [symbolicEngine.q, symbolicEngine.v, symbolicEngine.u, iH], [linear_c],
                                     ['q', 'v', 'u', 'iH'], ['c'])

    c_function_name = casadi_cCodeFilename+'.c'
    so_function_name = casadi_cCodeFilename+'.so'

    current_cwd = os.getcwd()
    if os.path.isdir(path):
        os.chdir(path)
    else:
        os.mkdir(path)
        os.chdir(path)

    CG = CodeGenerator(c_function_name)
    CG.add(g_linearization_A)
    CG.add(g_linearization_B)
    CG.add(g_linearization_c)
    CG.generate()

    command = "gcc -fPIC -shared " + c_function_name + " -o " + so_function_name
    print("Running " + command)

    os.system(command)

    os.chdir(current_cwd)
    print("Generated C code!")

    return {"functionName_A": functionName_A,
            "functionName_B": functionName_B,
            "functionName_c": functionName_c,
            "casadi_cCodeFilename": casadi_cCodeFilename,
            "path": path,
            "dofConfigurationSpaceRobot": n,
            "dofStateSpaceRobot": 2 * n,
            "dofControl": m}