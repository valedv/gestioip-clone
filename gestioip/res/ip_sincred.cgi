#!/usr/bin/perl -w

# Copyright (C) 2011 Marc Uebel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


use strict;
use Net::Ping::External qw(ping);
use lib '../modules';
use GestioIP;
use Net::IP;
use Net::IP qw(:PROC);
use Parallel::ForkManager;
use Socket;
use Math::BigInt;


my $start_time=time();

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten);

my $base_uri=$gip->get_base_uri();
my $server_proto=$gip->get_server_proto();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

if ( $client_id !~ /^\d{1,4}$/ ) {
	$client_id = 1;        
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{llenar_red_message}","$vars_file");
        $gip->print_error("$client_id","$$lang_vars{formato_malo_message}");
}

my @config = $gip->get_config("$client_id");
my $max_procs = $config[0]->[1] || "254";
my $ignorar = $config[0]->[2] || "";
my $ignore_generic_auto = $config[0]->[3] || "yes";
my $generic_dyn_host_name = $config[0]->[4] || "";
my $dyn_ranges_only = $config[0]->[5] || "n";
my $ping_timeout = $config[0]->[6] || "2";

my $red_num;
if ( $daten{'red_num'} !~ /^\d{1,5}$/ ) {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{llenar_red_message}","$vars_file");
	$gip->print_error("$client_id","$$lang_vars{formato_malo_message}");
} else {
	$red_num=$daten{'red_num'};
}

my @values_ignorar;
if ( $ignorar ) {
	@values_ignorar=split(",",$ignorar);
} else {
	$values_ignorar[0]="__IGNORAR__";
}
$generic_dyn_host_name =~ s/,/|/g;

my @values_redes = $gip->get_red("$client_id","$red_num");

if ( ! $values_redes[0] ) {
	$gip->print_error("$client_id","$$lang_vars{algo_malo_message}");
}

my $red = "$values_redes[0]->[0]" || "";
my $BM = "$values_redes[0]->[1]" || "";
my $descr = "$values_redes[0]->[2]" || "";
my $loc_id = "$values_redes[0]->[3]" || "";
my $ip_version = "$values_redes[0]->[7]" || "";
my $redob = "$red/$BM";
my $host_loc = $gip->get_loc_from_redid("$client_id","$red_num");
$host_loc = "---" if $host_loc eq "NULL";
my $host_cat = "---";

if ( $dyn_ranges_only eq "y" ) {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{llenar_red_message} $red/$BM $$lang_vars{reserved_ranges_only_message}","$vars_file");
} else {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{llenar_red_message} $red/$BM","$vars_file");
}

$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)") if $ip_version !~ /^(v4|v6)$/;

my $module = "Net::DNS";
my $module_check=$gip->check_module("$module") || "0";
$gip->print_error("$client_id","$$lang_vars{net_dns_not_found_message}") if $module_check != "1";


my $ipob = new Net::IP ($redob) or $gip->print_error("$client_id","$$lang_vars{comprueba_red_BM_message}: <b>$red/$BM</b>"); 
my $redint=($ipob->intip());
$redint = Math::BigInt->new("$redint");
my $first_ip_int = $redint + 1;
$first_ip_int = Math::BigInt->new("$first_ip_int");
my $last_ip_int = ($ipob->last_int());
$last_ip_int = Math::BigInt->new("$last_ip_int");
$last_ip_int = $last_ip_int - 1;

my $cat_id="-1";
my $int_admin="n";
my $utype="dns";
my $utype_id=$gip->get_utype_id("$client_id","$utype");

my $mydatetime = time();

print <<EOF;

<SCRIPT LANGUAGE="Javascript" TYPE="text/javascript">
<!--

function scrollToTop() {
  var x = '0';
  var y = '0';
  window.scrollTo(x, y);
  eraseCookie('net_scrollx')
  eraseCookie('net_scrolly')
}

// -->
</SCRIPT>

EOF


print "<div id=\"SincButtons\">\n";
if ( $BM >= 20 ) { 
	print "<table border=\"0\" width=\"100%\"><tr><td align=\"right\"><td align=\"right\"><form method=\"POST\" action=\"$server_proto://$base_uri/ip_show.cgi\" style=\"display:inline\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input name=\"ip_version\" type=\"hidden\" value=\"$ip_version\"><input type=\"submit\" class=\"detailed_view_button\" value=\"\" title=\"detailed network view\"name=\"B1\"></form><form method=\"POST\" action=\"$server_proto://$base_uri/ip_show_red_overview.cgi\" style=\"display:inline\"><input type=\"hidden\" name=\"view\" value=\"long\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input name=\"ip_version\" type=\"hidden\" value=\"$ip_version\"><input type=\"submit\" class=\"long_view_button\" value=\"\" title=\"network overview\" name=\"B1\"></form><form method=\"POST\" action=\"$server_proto://$base_uri/ip_show_red_overview.cgi\" style=\"display:inline\"><input type=\"hidden\" name=\"view\" value=\"short\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input name=\"ip_version\" type=\"hidden\" value=\"$ip_version\"><input type=\"submit\" class=\"short_view_button\" value=\"\" title=\"network status view\" name=\"B1\"></form></td></tr></table>\n";
} else {
	print "<table border=\"0\" width=\"100%\"><tr><td align=\"right\"><td align=\"right\"><form method=\"POST\" action=\"$server_proto://$base_uri/ip_show.cgi\" style=\"display:inline\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input name=\"ip_version\" type=\"hidden\" value=\"$ip_version\"><input type=\"submit\" class=\"detailed_view_button\" value=\"\" title=\"detailed network view\"name=\"B1\"></form></td></tr></table>\n";
}
print "</div>\n";

my @client_entries=$gip->get_client_entries("$client_id");
my $default_resolver = $client_entries[0]->[20];
my @dns_servers =("$client_entries[0]->[21]","$client_entries[0]->[22]","$client_entries[0]->[23]");

my $j=0;
my $hostname;
my ( $ip_int, $ip_bin, $ip_ad, $pm, $res, $pid, $ip );
my ( %res_sub, %res, %result);

my $MAX_PROCESSES=$max_procs || "254";
$pm = new Parallel::ForkManager($MAX_PROCESSES);

$pm->run_on_finish(
	sub { my ($pid, $exit_code, $ident) = @_;
		$res_sub{$pid}=$exit_code;
	}
);
$pm->run_on_start(
	sub { my ($pid,$ident)=@_;
		$res{$pid}="$ident";
	}
);


my $res_dns;
my $dns_error = "";

if ( $default_resolver eq "yes" ) {
	$res_dns = Net::DNS::Resolver->new(
	retry       => 2,
	udp_timeout => 5,
	recurse     => 1,
	debug       => 0,
	);
} else {
	$res_dns = Net::DNS::Resolver->new(
	retry       => 2,
	udp_timeout => 5,
	nameservers => [@dns_servers],
	recurse     => 1,
	debug       => 0,
	);
}

my $test_ip_int=$first_ip_int;
my $test_ip=$gip->int_to_ip("$client_id","$test_ip_int","$ip_version");

my $ptr_query=$res_dns->query("$test_ip");

if ( ! $ptr_query) {
	if ( $res_dns->errorstring eq "query timed out" ) {
		$gip->print_error("$client_id","$$lang_vars{no_answer_from_dns_message} - $$lang_vars{check_nameserver_message}<p>$$lang_vars{skipping_update_message}");
	}
}


my $used_nameservers = $res_dns->nameservers;

my $all_used_nameservers = join (" ",$res_dns->nameserver());

if ( $used_nameservers eq "0" ) {
	$gip->print_error("$client_id","$$lang_vars{no_answer_from_dns_message} - $$lang_vars{check_nameserver_message}<p>$$lang_vars{skipping_update_message}");
}
if ( $all_used_nameservers eq "127.0.0.1" && $default_resolver eq "yes" ) {
	$gip->print_error("$client_id","$$lang_vars{no_answer_from_dns_message} - $$lang_vars{check_nameserver_message}<p>$$lang_vars{skipping_update_message}");
}


for (my $i = $first_ip_int; $i <= $last_ip_int; $i++) {
	my $exit;
	$ip_ad=$gip->int_to_ip("$client_id","$i","$ip_version");
	
		##fork
		$pid = $pm->start("$ip_ad") and next;
			#child
			my $p = "";
			if ( $ip_version eq "v4" ) {
				$p = ping(host => "$ip_ad", timeout => $ping_timeout);
			} else {
				my $command='ping6 -c 1 ' .  $ip_ad;
				my $result=$gip->ping6_system("$command","0");
				$p=1 if $result == "0";
				
			}
			if ( $p ) {
				$exit=0;
			} else {
				$exit=1;
			}

			my ($ptr_query,$dns_result_ip);

			if ( $default_resolver eq "yes" ) {
				$res_dns = Net::DNS::Resolver->new(
				retry       => 2,
				udp_timeout => 5,
				recurse     => 1,
				debug       => 0,
				);
			} else {
				$res_dns = Net::DNS::Resolver->new(
				retry       => 2,
				udp_timeout => 5,
				nameservers => [@dns_servers],
				recurse     => 1,
				debug       => 0,
				);
			}

#			if ( $default_resolver eq "yes" ) {
#				$res_dns = Net::DNS::Resolver->new;
#			} else {
#
#				$res_dns = Net::DNS::Resolver->new(
#					nameservers => [@dns_servers],
#					recurse     => 1,
#					debug       => 0,
#				);
#			}

#			$res_dns->udp_timeout(10);

			if ( $ip_ad =~ /\w+/ ) {
				$ptr_query = $res_dns->search("$ip_ad");

				if ($ptr_query) {
					foreach my $rr ($ptr_query->answer) {
						next unless $rr->type eq "PTR";
						$dns_result_ip = $rr->ptrdname;
					}
				} else {
					$dns_error = $res_dns->errorstring;
				}
			}
			

			if ( $dns_error =~ /(query timed out|no nameservers)/ ) {
#				print "$$lang_vars{no_answer_from_dns_message}<br>";
				exit 5;
			} else {
				if ( $dns_result_ip && $exit == 0 ) {
					$exit=2;
				} elsif ( $dns_result_ip && $exit == 1 ) {
					$exit=3;
				} elsif ( ! $dns_result_ip && $exit == 0 ) {
					$exit=4;

				}
			}
		$pm->finish($exit); # Terminates the child process

}

$pm->wait_all_children;


while (($pid,$ip) = each ( %res )) {
	$result{$ip}=$res_sub{$pid};
}

my @ip;
if ( $dyn_ranges_only eq "y" ) {
	@ip=$gip->get_host_rango("$client_id","$first_ip_int","$last_ip_int");
} else {
	@ip=$gip->get_host("$client_id","$first_ip_int","$last_ip_int");
}

print "<span class=\"sinc_text\">";

my $k = 0;
for (my $i = $first_ip_int; $i <= $last_ip_int; $i++) {

	$ip_ad = $gip->int_to_ip("$client_id","$i","$ip_version");
	my $exit=$result{$ip_ad}; 


	my $range_id="-1";
	$range_id= $ip[$k]->[10] if $ip[$k]->[10] && $i eq $ip[$k]->[0];


	if ( defined($ip[$k]->[0]) ) {
		if ( $dyn_ranges_only eq "y" && $range_id == "-1" && $i eq $ip[$k]->[0] ) {
			$k++;
			next;
		} elsif ( $dyn_ranges_only eq "y" && $range_id == "-1" && $i ne $ip[$k]->[0] ) {
			next;
		}
	} elsif ( ! defined($ip[$k]->[0]) && $dyn_ranges_only eq "y" ) {
		next;
	}

	print "<b>$ip_ad</b>: "; 

	my $hostname_bbdd;
	my $cat_id="-1";
	my $int_admin="n";
	my $utype="dns";
	my $utype_id;
	my $host_descr = "NULL";
	my $comentario = "NULL";

	if ( defined($ip[$k]->[0]) ) {
		if ( ( $ip[$k]->[1] || $ip[$k]->[10] ne "-1" ) && $i eq $ip[$k]->[0] ) {
			$hostname_bbdd = $ip[$k]->[1];
			$host_descr = $ip[$k]->[2] if $ip[$k]->[2];
			$cat_id=$gip->get_cat_id("$client_id","$ip[$k]->[4]") if $ip[$k]->[4];
			$int_admin=$ip[$k]->[5] if $ip[$k]->[5];
			$comentario = $ip[$k]->[6] if $ip[$k]->[6];
			$utype=$ip[$k]->[7] if $ip[$k]->[7];
			$utype= "---" if $utype eq "NULL"; 
			$utype_id=$gip->get_utype_id("$client_id","$utype") || "-1";
			$range_id = $ip[$k]->[10] if $ip[$k]->[10];
			
		}
	}

	$utype_id=$gip->get_utype_id("$client_id","$utype") if ! $utype_id;

	my $ping_result=0;
	$ping_result=1 if $exit == "0" || $exit == "2" || $exit == "4";;

	# Ignor IP if update type has higher priority than "dns" 
	if ( $utype ne "dns" && $utype ne "---" ) {
		if ( $hostname_bbdd || $range_id ne "-1" ) {
			$k++;
		}
		if ( $hostname_bbdd ) {
			print "$hostname_bbdd - update type: $utype - $$lang_vars{ignorado_message}<br>\n";
			$gip->update_host_ping_info("$client_id","$i","$ping_result");
		} else {
			print "update type: $utype - $$lang_vars{ignorado_message}<br>\n";
		}
		next;
	}
		
	my $ignor_reason=0; # 1: no dns entry; 2: hostname matches generic-auto-name; 3: hostname matches ignore-string 4: hostname matches generic-dynamic name
	my @dns_result_ip;
	my $hostname;
	if ( $exit == 2 || $exit == 3 ) {

		my ($ptr_query,$dns_result_ip);

		if ( $default_resolver eq "yes" ) {
			$res_dns = Net::DNS::Resolver->new;
		} else {

			$res_dns = Net::DNS::Resolver->new(
				nameservers => [@dns_servers],
				recurse     => 1,
				debug       => 0,
			);
		}

		$res_dns->udp_timeout(10);

		if ( $ip_ad =~ /\w+/ ) {
			$ptr_query = $res_dns->search("$ip_ad");

			if ($ptr_query) {
				foreach my $rr ($ptr_query->answer) {
					next unless $rr->type eq "PTR";
					$dns_result_ip = $rr->ptrdname;
				}
			} else {
				$dns_error = $res_dns->errorstring;
			}
		}


		$hostname = $dns_result_ip || "unknown";


		if ( $hostname eq "unknown" ) {
			$ignor_reason=1;
		}
	} else {
		$hostname = "unknown";
		$ignor_reason=1;
	}


	my $ptr_name = $ip_ad;
	my $generic_auto="";
	if ( $ip_version eq "v4" ) {
		$ptr_name =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
		$generic_auto = "$2-$3-$4|$4-$3-$2|$1-$2-$3|$3-$2-$1";
	} else {
		$ptr_name =~ /^(\w+):(\w+):(\w+):(\w+):(\w+):(\w+):(\w+):(\w+)$/;
		$generic_auto = "$2-$3-$4|$4-$3-$2|$1-$2-$3|$3-$2-$1";
	}

	my $igno_name;
	my $igno_set = 0;

	if ( $hostname =~ /$generic_auto/ && $ignore_generic_auto eq "yes" ) {
		$igno_set = 1;
		$hostname="unknown";
		$igno_name="$generic_auto";
		$ignor_reason=2;
	}

	foreach (@values_ignorar) {
		if ( $hostname =~ /$_/ ) {
			$igno_set = 1;
			$hostname="unknown";
			$igno_name="$_";
			$ignor_reason=3;
		}
		next;
	}

	if ( $hostname =~ /$generic_dyn_host_name/ ) {
		$igno_set = 1;
		$hostname="unknown";
		$igno_name="$generic_dyn_host_name";
		$ignor_reason=4;
	}

	if ( $hostname_bbdd ) {

		if ( $hostname_bbdd eq $hostname && $hostname ne "unknown" && $igno_set == "0") {
			print "$$lang_vars{tiene_entrada_message}: $hostname_bbdd - $$lang_vars{ignorado_message}<br>\n";
			$gip->update_host_ping_info("$client_id","$i","$ping_result");

		} else {
			if ( $hostname eq "unknown" && $hostname_bbdd !~ /$generic_dyn_host_name/ && $ping_result == "0" ) {
				if ( $range_id eq "-1" ) {
					my $host_id=$gip->get_host_id_from_ip_int("$client_id","$i");
					$gip->delete_custom_host_column_entry("$client_id","$host_id");
					$gip->delete_ip("$client_id","$i","$i");
				} else {
					my $host_id=$gip->get_host_id_from_ip_int("$client_id","$i");
					$gip->delete_custom_host_column_entry("$client_id","$host_id");
					$gip->clear_ip("$client_id","$i","$i");
				}
				# no dns entry
				if ( $ignor_reason == "1" ) {
					print "$$lang_vars{entrada_borrado_message}: $hostname_bbdd ($$lang_vars{no_dns_message} + $$lang_vars{no_ping_message})<br>\n";
				# generic auto name
				} elsif ( $ignor_reason == "2" ) {
					print "$$lang_vars{entrada_borrado_message}: $hostname_bbdd ($$lang_vars{generico_message} + $$lang_vars{no_ping_message})<br>\n";
				# hostname matches ignore-string
				} elsif ( $ignor_reason == "3" ) {
					print "$$lang_vars{entrada_borrado_message}: $hostname_bbdd ($$lang_vars{tiene_string_no_ping_message} \"$igno_name\")<br>\n";
				} else {
					print "$$lang_vars{entrada_borrado_message}: $hostname_bbdd ($$lang_vars{no_ping_message})<br>\n";
				}
				$k++;
				my $audit_type="14";
				my $audit_class="1";
				my $update_type_audit="6";
				my $host_descr_audit = $host_descr;
				$host_descr_audit = "---" if $host_descr_audit eq "NULL";
				my $comentario_audit = $comentario;
				$comentario_audit = "---" if $comentario_audit eq "NULL";
				my $event="$ip_ad,$hostname_bbdd,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
				$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
				next;
			} elsif ( $hostname eq "unknown" && $hostname_bbdd =~ /$generic_dyn_host_name/ && $ping_result == "0" ) {
				if ( $range_id eq "-1" ) {
					my $host_id=$gip->get_host_id_from_ip_int("$client_id","$i");
					$gip->delete_custom_host_column_entry("$client_id","$host_id");
					$gip->delete_ip("$client_id","$i","$i");
				} else {
					my $host_id=$gip->get_host_id_from_ip_int("$client_id","$i");
					$gip->delete_custom_host_column_entry("$client_id","$host_id");
					$gip->clear_ip("$client_id","$i","$i");
				}
				print "$$lang_vars{entrada_borrado_message}: $hostname_bbdd ($$lang_vars{generic_dyn_host_message} + $$lang_vars{no_ping_message})<br>\n";
				$k++;
				my $audit_type="14";
				my $audit_class="1";
				my $update_type_audit="6";
				my $host_descr_audit = $host_descr;
				$host_descr_audit = "---" if $host_descr_audit eq "NULL";
				my $comentario_audit = $comentario;
				$comentario_audit = "---" if $comentario_audit eq "NULL";
				my $event="$ip_ad,$hostname_bbdd,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
				$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
				next;
			} elsif ( $hostname eq "unknown" && $ping_result == "1" ) {
				# no dns entry
				if ( $ignor_reason == "1" ) {
					print "$$lang_vars{tiene_entrada_message}: $hostname_bbdd ($$lang_vars{no_dns_message}) - $$lang_vars{ignorado_message}<br>\n";
				# generic auto name
				} elsif ( $ignor_reason == "2" ) {
					print "$$lang_vars{tiene_entrada_message}: $hostname_bbdd - $$lang_vars{ignorado_message}<br>\n";
				# hostname matches ignore-string
				} elsif ( $ignor_reason == "3" ) {
					print "$$lang_vars{tiene_entrada_message}: $hostname_bbdd - $$lang_vars{ignorado_message}<br>\n";
				# hostname matches generic-dynamic name
				} elsif ( $ignor_reason == "4" ) {
					print "$$lang_vars{tiene_entrada_message}: $hostname_bbdd - $$lang_vars{ignorado_message}<br>\n";
				}
				$gip->update_host_ping_info("$client_id","$i","$ping_result");
				$k++;
				next;
			}

			if ( $hostname_bbdd ne $hostname ) {
					$gip->update_ip_mod("$client_id","$i","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$ping_result");
					print "$$lang_vars{entrada_actualizada_message}: $hostname ($$lang_vars{entrada_antigua_message}: $hostname_bbdd)<br>\n";

				my $audit_type="1";
				my $audit_class="1";
				my $update_type_audit="6";
				my $host_descr_audit = $host_descr;
				$host_descr_audit = "---" if $host_descr_audit eq "NULL";
				my $comentario_audit = $comentario;
				$comentario_audit = "---" if $comentario_audit eq "NULL";
#				my $event="$ip_ad,$hostname,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
#				my $event="$ip_ad:$hostname_bbdd -> $hostname";
				my $event="$ip_ad: $hostname_bbdd,$host_descr_audit,$host_loc,$host_cat,$comentario_audit -> $hostname,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
				$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");

			} elsif ( $ping_result == 1 && $hostname_bbdd eq "unknown" && $hostname eq "unknown" ) {
				print "$$lang_vars{tiene_entrada_message}: $hostname_bbdd - ($$lang_vars{generico_message}) $$lang_vars{ignorado_message}<br>\n";
				$gip->update_host_ping_info("$client_id","$i","$ping_result");

			} else {
				$gip->update_host_ping_info("$client_id","$i","$ping_result");
				print "$hostname_bbdd: $$lang_vars{entrada_cambiado_message} (DNS: $hostname) - $$lang_vars{ignorado_message} ($$lang_vars{update_type_message}: $utype)<br>\n";
			}
		}
		$k++;
		next;
	}

	# no hostname_bbdd; 2: dns ok, ping ok; 3: dns ok, ping failed; 4: DNS not ok, ping OK
	if ( $exit eq 2 || $exit eq 3 || $exit eq 4 ) {
		if ( $exit eq 3 && $hostname eq "unknown" && $igno_set == "1" ) {
			print "$$lang_vars{tiene_string_no_ping_message} \"$igno_name\" - $$lang_vars{ignorado_message}<br>\n";
			if ( $range_id ne "-1" ) {
				$k++;
			}
			next;
		}
		if ( $range_id eq "-1" ) {
			$gip->insert_ip_mod("$client_id","$i","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$ping_result");
		} else {
			$gip->update_ip_mod("$client_id","$i","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$ping_result");
			$k++;
		}
		if ( $exit eq 2 && $hostname eq "unknown" && $igno_set == "1") {
			print "$$lang_vars{tiene_string_message} \"$igno_name\" - $$lang_vars{host_anadido_message}: unknown<br>\n";
		} else {
			print "$$lang_vars{host_anadido_message}: $hostname<br>\n";
		}
		my $audit_type="15";
		my $audit_class="1";
		my $update_type_audit="6";
		my $host_descr_audit = $host_descr;
		$host_descr_audit = "---" if $host_descr_audit eq "NULL";
		my $comentario_audit = $comentario;
		$comentario_audit = "---" if $comentario_audit eq "NULL";
#		my $event="$ip_ad: $hostname_bbdd,$host_descr_audit,$host_loc,$host_cat,$comentario_audit -> $hostname,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
		my $event="$ip_ad: $hostname,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
		$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
	} else {
		print "$$lang_vars{no_dns_message} + $$lang_vars{no_ping_message} - $$lang_vars{ignorado_message}<br>\n";
		if ( $range_id ne "-1" ) {
			$k++;
		}
	} 
}

print "</span>";

my $audit_type="4";
my $audit_class="2";
my $update_type_audit="6";
my $event="$red/$BM";
$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");

print "<h3>$$lang_vars{listo_message}</h3>\n";

my $end_time=time();
my $duration=$end_time - $start_time;
my @parts = gmtime($duration);
my $duration_string = "";
$duration_string = $parts[2] . "h, " if $parts[2] != "0";
$duration_string = $duration_string . $parts[1] . "m";
$duration_string = $duration_string . " and " . $parts[0] . "s";
print "<i>$$lang_vars{execution_time_message}: ${duration_string}</i><p>\n";


$gip->print_end("$client_id","$vars_file","go_to_top");
