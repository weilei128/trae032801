from typing import Dict, Any, List
from ssh_client import SSHClient
import json


class DockerCollector:
    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client

    def check_docker_installed(self) -> bool:
        exit_code, _, _ = self.ssh.execute_command("which docker")
        return exit_code == 0

    def get_docker_info(self) -> Dict[str, Any]:
        result = {
            'installed': False,
            'version': '',
            'running': False,
            'containers_total': 0,
            'containers_running': 0,
            'containers_stopped': 0,
            'images_count': 0,
            'storage_driver': '',
            'docker_root_dir': ''
        }
        
        if not self.check_docker_installed():
            return result
        
        result['installed'] = True
        
        exit_code, output, _ = self.ssh.execute_command("docker --version")
        if exit_code == 0 and output:
            result['version'] = output.strip()
        
        exit_code, output, _ = self.ssh.execute_command("docker info --format '{{.ServerVersion}}' 2>/dev/null")
        if exit_code == 0 and output.strip():
            result['running'] = True
            
            exit_code, output, _ = self.ssh.execute_command("docker info --format '{{.Driver}}' 2>/dev/null")
            if exit_code == 0:
                result['storage_driver'] = output.strip()
            
            exit_code, output, _ = self.ssh.execute_command("docker info --format '{{.DockerRootDir}}' 2>/dev/null")
            if exit_code == 0:
                result['docker_root_dir'] = output.strip()
        
        return result

    def get_containers(self) -> List[Dict[str, Any]]:
        result = []
        
        if not self.check_docker_installed():
            return result
        
        exit_code, output, _ = self.ssh.execute_command(
            "docker ps -a --format '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}|{{.State}}'"
        )
        
        if exit_code == 0 and output:
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 6:
                        container_id = parts[0]
                        name = parts[1]
                        image = parts[2]
                        status = parts[3]
                        ports = parts[4]
                        state = parts[5]
                        
                        result.append({
                            'id': container_id,
                            'name': name,
                            'image': image,
                            'status': status,
                            'ports': ports,
                            'state': state,
                            'is_running': state == 'running'
                        })
        
        return result

    def get_container_stats(self) -> List[Dict[str, Any]]:
        result = []
        
        if not self.check_docker_installed():
            return result
        
        exit_code, output, _ = self.ssh.execute_command(
            "docker stats --no-stream --format '{{.Container}}|{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}|{{.BlockIO}}'"
        )
        
        if exit_code == 0 and output:
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 7:
                        result.append({
                            'container_id': parts[0],
                            'name': parts[1],
                            'cpu_percent': parts[2],
                            'mem_usage': parts[3],
                            'mem_percent': parts[4],
                            'net_io': parts[5],
                            'block_io': parts[6]
                        })
        
        return result

    def get_images(self) -> List[Dict[str, Any]]:
        result = []
        
        if not self.check_docker_installed():
            return result
        
        exit_code, output, _ = self.ssh.execute_command(
            "docker images --format '{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}|{{.CreatedAt}}'"
        )
        
        if exit_code == 0 and output:
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        result.append({
                            'repository': parts[0],
                            'tag': parts[1],
                            'id': parts[2],
                            'size': parts[3],
                            'created': parts[4]
                        })
        
        return result

    def get_docker_summary(self) -> Dict[str, Any]:
        containers = self.get_containers()
        images = self.get_images()
        docker_info = self.get_docker_info()
        
        running_count = sum(1 for c in containers if c['is_running'])
        
        return {
            'installed': docker_info['installed'],
            'running': docker_info['running'],
            'version': docker_info['version'],
            'containers_total': len(containers),
            'containers_running': running_count,
            'containers_stopped': len(containers) - running_count,
            'images_count': len(images),
            'storage_driver': docker_info['storage_driver'],
            'docker_root_dir': docker_info['docker_root_dir']
        }
