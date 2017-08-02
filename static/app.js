var robotApp = angular.module('robotApp', []);
robotApp.controller('RobotController', function ($scope, $http, $interval, socket) {

    var uuidv4 = function () {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    $scope.directions = [4,5,6,7,8,1,2,3];
    $scope.uuid = uuidv4();
    $scope.data = {
        selected: null,
        direction: null,
        magnitude: 0,
        n_controllers: 0,
        total_counts: {}
    }
    $scope.min = window.Math.min;

    socket.emit('client_ready');

    $scope.set_direction = function(i) {
        $scope.data.selected = i;
        $scope.send_instruction()
    }

    $scope.send_instruction = function() {
        socket.emit('instruction', {
            user: $scope.uuid,
            direction: $scope.data.selected,
        })
    }

    // Instruction timeout is 3 second, ping to ensure we stay live
    setInterval($scope.send_instruction, 1500);

    // Receive updated signal via socket and apply data
    socket.on('updated_status', function (data) {
        $scope.data.direction = data.direction;
        $scope.data.magnitude = data.magnitude;
        $scope.data.n_controllers = data.n_controllers
        $scope.data.total_counts = data.total_counts;
      });

    // Receive updated signal via socket and apply data
    socket.on('updated_image', function (data) {
        blob = new Blob([data], {type: "image/jpeg"});
        $scope.data.imageUrl = window.URL.createObjectURL(blob);
      });


 });


robotApp.factory('socket', function ($rootScope) {
  var socket = io.connect();
  return {
    on: function (eventName, callback) {
      socket.on(eventName, function () {
        var args = arguments;
        $rootScope.$apply(function () {
          callback.apply(socket, args);
        });
      });
    },
    emit: function (eventName, data, callback) {
      socket.emit(eventName, data, function () {
        var args = arguments;
        $rootScope.$apply(function () {
          if (callback) {
            callback.apply(socket, args);
          }
        });
      })
    }
  };
});