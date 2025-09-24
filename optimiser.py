from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def optimize_route(locations):
    # locations: list of (lat, lng)
    n = len(locations)
    if n <= 1:
        return list(range(n))
    
    # distance callback
    def distance_callback(i, j):
        if i == j:
            return 0
        from geopy.distance import geodesic
        # Return distance in meters, rounded to integer, capped at reasonable maximum
        dist = geodesic(locations[i], locations[j]).meters
        return min(int(round(dist)), 999999)  # Cap at ~1000km

    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    
    # Register the distance callback
    def distance_evaluator(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_callback(from_node, to_node)
        except Exception as e:
            print(f"Error in distance_evaluator: {e}, from_index={from_index}, to_index={to_index}")
            return 999999  # Return large distance on error
    
    transit_callback_index = routing.RegisterTransitCallback(distance_evaluator)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    solution = routing.SolveWithParameters(search_parameters)
    
    order = []
    if solution:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            order.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
    return order
